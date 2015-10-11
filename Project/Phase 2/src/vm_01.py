from flask import Flask,request
from flask import render_template
from flask import jsonify
from flask.ext.mongoengine import MongoEngine
from pymongo import read_preferences
from flask.ext.mongoengine.wtf import model_form
import json
import libvirt
import os
import uuid
import rbd
import sys
import rados
from random import choice
import xml.etree.ElementTree as ET

app = Flask(__name__)

app.config["MONGODB_SETTINGS"] = {'DB': "test",'read_preference': read_preferences.ReadPreference.PRIMARY}
db = MongoEngine(app)

#### MongoDB Classes ####

class Vm(db.Document):
	name = db.StringField(required=True)
	instance_type = db.StringField(required=True)
	image_id = db.StringField(required=True)
	vmid = db.StringField(required=True)
	pmid = db.StringField(required=True)
	pm = db.StringField(required=True)
	
class Volume(db.Document):
	volid = db.StringField(required=True)
	name = db.StringField(required=True)
	vmid = db.StringField(default="0")
	size = db.StringField(required=True)
	dev_name = db.StringField(required=True)
	status = db.StringField(default="available")

#### Global Variables ####
image_paths = []
pm_paths = []
pm_next = 0
rbdInstance = rbd.RBD()
pool_name = 'first'
BLOCK_CONFIG_XML = './attach.xml'

#### Connection ####
radosConnection = rados.Rados(conffile='/etc/ceph/ceph.conf')
radosConnection.connect()
if pool_name not in radosConnection.list_pools():                                
	radosConnection.create_pool(pool_name)
ioctx = radosConnection.open_ioctx(pool_name)
rbdInstance = rbd.RBD()

@app.route('/')
def index():
	return "Cloud Project - 201356204"

@app.route('/vm/create')
def create():
	error = ""
	name = request.args.get('name')
	instance_type = request.args.get('instance_type')
	image_id = request.args.get('image_id')
	if name == None or instance_type == None or image_id == None:
		error = "Arguments are null"
		return error
	else:
		instance_type = int(instance_type)
		image_id = int(image_id)
		file_data = open(sys.argv[3],'r')
		json_data = json.load(file_data)
		cpu = json_data['types'][instance_type-1]['cpu']
	 	ram = json_data['types'][instance_type-1]['ram']
	 	disk = json_data['types'][instance_type-1]['disk']
		image_path = ""
		if len(image_paths) >= image_id:
			image_path = image_paths[image_id-1]
	 	else:
	 		error = "Image Id not found"
			return error
	 	chosen = choose_pm(ram,cpu,image_path)
		if chosen == -1:
	 		error = "Not enoungh Physical machines"
			return error
		try:
			connection = libvirt.open("qemu+ssh://"+pm_paths[chosen]+"/system")
			list_domains = connection.listDomainsID()
			vmid = 0
			if len(list_domains) != 0:
				vmid = max(list_domains) + 1
			else:
				vmid = 1
			send_image(pm_paths[chosen],image_path)
			image_path = "/home/"+pm_paths[chosen].split("@")[0]+"/"+image_path.split("/")[-1]
			xml = """
	    <domain type='qemu' id='%s'>
	        <name>%s</name>
	        <memory unit='KiB'>%s</memory>
	        <currentMemory unit='KiB'>524</currentMemory>
	        <vcpu>%s</vcpu>
	        <os>
	            <type arch='x86_64' machine='pc-1.1'>hvm</type>
	            <boot dev='cdrom'/>
	            <boot dev='hd'/>
	        </os>
	        <features>
	            <acpi/>
	            <apic/>
	            <pae/>
	        </features>
	        <clock offset='utc'/>
	        <on_poweroff>destroy</on_poweroff>
	        <on_reboot>restart</on_reboot>
	        <on_crash>restart</on_crash>
	        <devices>
	            <emulator>/usr/bin/kvm-spice</emulator>
	            <disk type='file' device='cdrom'>
	                <driver name='qemu' type='raw'/>
	                <target dev='hda' bus='ide'/>
	            </disk>
	            <disk type='file' device='cdrom'>
	                <driver name='qemu' type='raw'/>
	                <source file='%s'/>
	                <target dev='hdc' bus='ide'/>
	                <readonly/>
	            </disk>
	            <graphics type='spice' port='5900' autoport='yes' listen='127.0.0.1'>
	                <listen type='address' address='127.0.0.1'/>
	            </graphics>
	        </devices>
	    </domain>
	    """% (vmid, name, str(int(ram)*1000), str(cpu), str(image_path))
#			xml = """<domain type='qemu' id='%s'><name>%s</name><memory>%s</memory> <currentMemory>512000</currentMemory> <vcpu>%s</vcpu> <os> <type arch='i686' machine='pc-1.0'>hvm</type> <boot dev='hd'/> </os> <features> <acpi/> <apic/> <pae/> </features> <clock offset='utc'/> <on_poweroff>destroy</on_poweroff> <on_reboot>restart</on_reboot> <on_crash>restart</on_crash> <devices> <emulator>/usr/bin/qemu-system-i386</emulator> <disk type='file' device='disk'> <driver name='qemu' type='qcow2'/> <source file='%s' /> <target dev='hda' bus='ide'/> <alias name='ide0-0-0'/> <address type='drive' controller='0' bus='0' unit='0'/> </disk> <controller type='ide' index='0'> <alias name='ide0'/> <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x1' multifunction='on'/> </controller> <interface type='network'> <mac address='52:54:00:82:f7:43'/> <source network='default'/> <target dev='vnet0'/> <alias name='net0'/> <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0' multifunction='on'/> </interface> <serial type='pty'> <source path='/dev/pts/2'/> <target port='0'/> <alias name='serial0'/> </serial> <console type='pty' tty='/dev/pts/2'> <source path='/dev/pts/2'/> <target type='serial' port='0'/> <alias name='serial0'/> </console> <input type='mouse' bus='ps2'/> <graphics type='vnc' port='5900' autoport='yes'/> <sound model='ich6'> <alias name='sound0'/> <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0' multifunction='on'/> </sound> <video> <model type='cirrus' vram='9216' heads='1'/> <alias name='video0'/> <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0' multifunction='on'/> </video> <memballoon model='virtio'> <alias name='balloon0'/> <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0' multifunction='on'/> </memballoon> </devices> <seclabel type='dynamic' model='apparmor' relabel='yes'> <label>libvirt-10a963ef-9458-c30d-eca3-891efd2d5817</label> <imagelabel>libvirt-10a963ef-9458-c30d-eca3-891efd2d5817</imagelabel> </seclabel></domain>""" % (vmid, name, str(int(ram)*1000), str(cpu), str(image_path))
			connection.defineXML(xml)
			domain = connection.lookupByName(name)
			domain.create()
			connection.close()	
			storage_data = Vm(pm=pm_paths[chosen],name=name,vmid=str(vmid),instance_type=str(instance_type), image_id=str(image_id),pmid=str(chosen+1)).save()
			return jsonify(vmid=vmid)
		except TypeError:
			return jsonify(status=0)
		except libvirt.libvirtError:
		 	return jsonify(status=0)

@app.route('/vm/query')
def query():
	try:
		error = ""
		vmid = request.args.get('vmid')
		if vmid != None:
			vm_data = Vm.objects.get(**{'vmid' : str(vmid)})
			connection = libvirt.open("qemu+ssh://"+vm_data.pm+"/system")
			domains = connection.lookupByName(vm_data.name)
			info_domain = domains.info()
			if info_domain[1] == 512000:
		        	ints_type = 1
			elif info_domain[1] == 1024000:
				ints_type = 2
			elif info_domain[1] == 2048000:
				ints_type = 3
			connection.close()
			return jsonify(vmid = vmid,pmid = vm_data.pmid,name = vm_data.name,instace_type = str(ints_type))
		else:
			return jsonify(status=0)
	except:
		return jsonify(status=0)

@app.route('/vm/destroy')
def destroy():
	try:
		error = ""
		vmid = request.args.get('vmid')
		if vmid != None:
			vm_data = Vm.objects.get(**{'vmid' : str(vmid)})
			connection = libvirt.open("qemu+ssh://"+vm_data.pm+"/system")
			domains = connection.lookupByName(vm_data.name)
		        try:
				domains.destroy()
				connection.close()
			        return jsonify(status=1)
		        except:
		        	connection.close()
				return jsonify(status=0)
		else:
			return jsonify(status=0)
	except:
		return jsonify(status=0)

@app.route('/vm/types')
def types():
	try:
		flavor_file = open(sys.argv[3] , "r")
		data = json.loads(flavor_file.read())
		return jsonify(data)
	except:
		return jsonify(status=0)

@app.route('/pm/listvms')
def list_vm():
	try:
		error = ""
		pmid = request.args.get('pmid')
		temp = []
		if pmid != None:
			for vm_data in Vm.objects(pmid=str(pmid)):
				temp.append(vm_data.vmid)
			return jsonify(vmids=temp)
		else:
			return jsonify(status=0)
	except:
		return jsonify(status=0)

@app.route('/pm/list')
def pm_list():
	try:
		error = ""
		pm_file = open(sys.argv[1] , "r")
		PM_list = []
		count = 1
		for i in pm_file.readlines():
			PM_list.append(count)
			count = count +1
		return jsonify(pmids=PM_list)
	except:
		return jsonify(status=0)

@app.route('/pm/query')
def pm_query():
	try:
		error = ""
		pmid = request.args.get('pmid')
		if pmid != None:
			pmid = int(pmid)
			if pmid <= len(pm_paths):
				os.system(" ssh " + pm_paths[pmid-1] +" nproc >> data_pm")
				os.system(" ssh " + pm_paths[pmid-1] +" cat /proc/meminfo | grep MemTotal | awk '{ print $2 }' >> data_pm")
				os.system(" ssh " + pm_paths[pmid-1] +" df --total -TH --exclude-type=tmpfs | awk '{print $3}' | tail -n 1 | cut -b -3 >> data_pm")
				file_data = open("data_pm", "r")
				pm_cpu =  file_data.readline().strip("\n")
				pm_ram = file_data.readline().strip("\n")
				pm_disk = file_data.readline().strip("\n")
				os.system("rm -rf data_pm")
				count = 0
				for vm_data in Vm.objects(pmid=str(pmid)):
					count = count + 1
				no_vms = count
				os.system(" ssh " + pm_paths[pmid-1] +" nproc >> data_pm")
				os.system(" ssh " + pm_paths[pmid-1] +" cat /proc/meminfo | grep MemFree | awk '{ print $2 }' >> data_pm")
				os.system(" ssh " + pm_paths[pmid-1] +" df --total -TH --exclude-type=tmpfs | awk '{print $5}' | tail -n 1 | cut -b -3 >> data_pm")
				file_data = open("data_pm", "r")
				free_cpu = file_data.readline().strip("\n")
				free_ram = file_data.readline().strip("\n")
				free_disk = file_data.readline().strip("\n")
				os.system("rm -rf data_pm")
				cap = {}
				cap['cpu'] = pm_cpu
				cap['ram'] = pm_ram
				cap['disk'] = pm_disk
				free = {}
				free['cpu'] = free_cpu
				free['ram'] = free_ram
				free['disk'] = free_disk
				return jsonify(pmid=pmid,capacity=cap,free=free)
			else:
				return jsonify(status=0)
		else:
			return jsonify(status=0)
	except:
		return jsonify(status=0)

@app.route('/image/list')
def img_list():
	try:
		error = ""
		image_file = open(sys.argv[2] , "r")
		count = 1
		images = []
		for i in image_file.readlines():
			imgs = {}
			imgs["id"] = count
			string_idk = i
			imgs["name"] = string_idk.strip('\n').split("/")[-1].rsplit(".",1)[0]
			images.append(imgs)
			count = count +1
		return jsonify(images=images)
	except:
		return jsonify(status=0)

#### Phase 2 ####

@app.route('/volume/create')
def volumeCreate():
	name = str(request.args.get('name'))
	size = int(request.args.get('size'))
	volume_data = ""
	if name == None or size == None:
		error = "Arguments are null"
		return error
	else:
		try:
			volume_data = Volume.objects.get(**{'name' : name})
		except:
			size = (1024**3) * size
			global ioctx
			global rbdInstance
			try:
	    			rbdInstance.create(ioctx,name,size)
	       			os.system('sudo rbd map %s --pool %s --name client.admin'%(name,pool_name))
	    		except:
	        		return jsonify(volumeid=0) 
	        	temp = str(uuid.uuid4())
			alpha = choice('efghijklmnopqrstuvwxyz')
			numeric = choice([x for x in range(1,10)])
			temp_name = 'sd' + str(alpha) + str(numeric)
			storage_data = Volume(volid=temp,name=name,size=str(size),dev_name=temp_name).save()
			return jsonify(volumeid=temp)
	return jsonify(volumeid=0)

@app.route("/volume/query")
def volumeQuery():
	volumeid = str(request.args.get('volumeid'))
	if volumeid == None:
		error = "Arguments are null"
		return error
	else:
		try:
			volume_data = Volume.objects.get(**{'volid' : volumeid})
			if volume_data.status == "available":
				return jsonify(volumeid = volumeid,
				               name = volume_data.name,
				               size = volume_data.size,
				               status = volume_data.status,
				               )
			elif volume_data.status == 'attached':
    				return jsonify(volumeid = volumeid,
                       		name = volume_data.name,
                       		size = volume_data.size,
                       		status = volume_data.status,
                       		vmid = volume_data.vmid,
                       		)
    		except:
    			return jsonify(error="volumeid : " + volumeid + " does not exist")

@app.route("/volume/destroy")
def volumeDestroy():
	volumeid = str(request.args.get('volumeid'))
	if volumeid == None:
		error = "Arguments are null"
		return error
	else:
		try:
			volume_data = Volume.objects.get(**{'volid' : volumeid})
			if volume_data.status == "attached":
				return jsonify(status=0)
			if volume_data.status == "available":
				image_name = str(volume_data.name)
				try:
        				os.system('sudo rbd unmap /dev/rbd/%s/%s'%(pool_name,image_name))
        				rbdInstance.remove(ioctx,image_name)
				except:
					return jsonify(status=0)  
        			volume_data.delete()
    				return jsonify(status=1)
   		except:
    			return jsonify(status=0)
	return jsonify(status=0)

@app.route("/volume/attach")
def volumeAttach():
	global pm_next
	vmid = int(request.args.get('vmid'))
	volumeid = str(request.args.get('volumeid'))
	if volumeid == None or vmid == None:
		error = "Arguments are null"
		return error
	else:
		try:
			volume_data = Volume.objects.get(**{'volid' : volumeid})
			if volume_data.status == "attached":
				return jsonify(status=0)
			try:
				vm_data = Vm.objects.get(**{'vmid' : str(vmid)})
				image_name = volume_data.name
				connection = libvirt.open("qemu+ssh://"+vm_data.pm+"/system")
				domains = connection.lookupByName(vm_data.name)
				info_domain = domains.info()
				config_xml = """<disk type='block' device='disk'>
					<driver name='qemu' type='raw'/>
					<source protocol='rbd' dev='/dev/rbd/%s/%s'>
						<host name='%s' port='6789'/>
					</source>
					<target dev='%s' bus='virtio'/>
					<address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
				</disk>"""%(pool_name, image_name, "10.1.36.68", volume_data.dev_name)
				try:
					domains.attachDevice(config_xml)
	        			connection.close()
				except:
					connection.close()
       					return jsonify(status=0) 
   				volume_data.status = "attached"
				volume_data.vmid = str(vmid)
				volume_data.save()
		    		return jsonify(status=1)
			except:
				return jsonify(status=0)
		except:
			return jsonify(status=0)
	return jsonify(status=0) 

@app.route("/volume/detach")
def volumeDetach():
	volumeid = str(request.args.get('volumeid',''))
	if volumeid == None:
		error = "Arguments are null"
		return error
	else:
		try:
			volume_data = Volume.objects.get(**{'volid' : volumeid})
			if volume_data.status == 'available':
				return jsonify(status=0)
			image_name = volume_data.name
			vm_data = Vm.objects.get(**{'vmid' : volume_data.vmid})
			connection = libvirt.open("qemu+ssh://"+ vm_data.pm+"/system")
			domains = connection.lookupByName(vm_data.name)
			config_xml = """<disk type='block' device='disk'>
                                         <driver name='qemu' type='raw'/>
                                       <source protocol='rbd' dev='/dev/rbd/%s/%s'>
                                            <host name='%s' port='6789'/>
                                      </source>
                                     <target dev='%s' bus='virtio'/>
                                       <address type='pci' domain='0x0000' bus='0x00' slot='0x05' function='0x0'/>
                              </disk>"""%(pool_name, image_name, "10.1.36.68", volume_data.dev_name)
			try:
				domains.detachDevice(config_xml)
				connection.close()
	    		except:
	            		connection.close()
			        return jsonify(status=0) 
	    		volume_data.status = "available"
			volume_data.vmid = "0"
			volume_data.save()
			return jsonify(status=1)
		except:
			return jsonify(status=0)
	return jsonify(status=0)
	
#### Function which help the above queries ####

def choose_pm(ram,cpu,image_path):
	global pm_next
	os.system(" ssh " + pm_paths[pm_next] +" free -k | grep 'Mem:' | awk '{ print $4 }' >> data_pm")
	os.system(" ssh " + pm_paths[pm_next] +" grep processor /proc/cpuinfo | wc -l >> data_pm")
	file_data = open("data_pm", "r")
	pm_ram = file_data.readline().strip("\n")
	pm_cpu = file_data.readline().strip("\n")
	os.system("rm -rf data_pm")
	bits = 32
	try:
		temp = (subprocess.check_output("ssh " + pm_paths[pm_next] + " cat /proc/cpuinfo | grep lm " ,shell=True))
		bits = '64'
	except:
		bits = '32'
	substring = "64"
	if substring in image_path:
		image_bit = 64
	else:
		image_bit = 32
	count = 0
	while(int(pm_ram) < int(ram) or int(pm_cpu) < int(cpu) or int(image_bit) > bits):
		if count == len(pm_paths):
			return -1
		pm_next = (pm_next + 1)%len(pm_paths)
		if pm_next == len(pm_paths):
			pm_next = 0
		os.system(" ssh " + pm_paths[pm_next] +" free -k | grep 'Mem:' | awk '{ print $4 }' >> data_pm")
		os.system(" ssh " + pm_paths[pm_next] +" grep processor /proc/cpuinfo | wc -l >> data_pm")
		file_data = open("data_pm", "r")
		pm_ram = file_data.readline().strip("\n")
		pm_cpu = file_data.readline().strip("\n")
		os.system("rm -rf data_pm")
		bits = 32
		try:
			temp = (subprocess.check_output("ssh " + pm_paths[pm_next] + " cat /proc/cpuinfo | grep lm " ,shell=True))
		 	bits = '64'
		except:
			bits = '32'
		substring = "64"
		if substring in image_path:
			image_bit = 64
		else:   
			image_bit = 32
		count = count + 1
	temp = pm_next
	pm_next = pm_next + 1
	if pm_next  == len(pm_paths):                                                      
		pm_next = 0          
	return temp

def store_images():
	file_data = open(sys.argv[2],'r')
	for i in file_data.readlines():
		image_paths.append(i.strip("\n"))

def store_pms():
	file_data = open(sys.argv[1],'r')
	for i in file_data.readlines():
		pm_paths.append(i.strip("\n"))

def send_image(pm, image_path):
	image_path = image_path.strip("\r")
	bash_command = "scp " + image_path + " " + pm + ":/home/" + pm.split("@")[0] + "/"
	os.system(bash_command)

if __name__ == '__main__':
	if len(sys.argv) < 4: 
		print "Format: ./script pm_file image_file flavor_file"
		exit(1)
	#### Pre Calling Functions for initial setup ####
	store_images()
	store_pms()
	app.run(debug=True)
