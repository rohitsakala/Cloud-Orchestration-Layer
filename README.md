Cloud-Orchestration-Layer
=========================

A Cloud Orchestration Layer: Creating/Deleting/Quering and Scheduling Virtual Machines(VMs) in a given Network and also attach Storage Block Devices to the VMs on demand

How does it work?

Write the information of the machines in file named: machines

And also the Location of the VM image file in file name: Images

cd bin

./script machines Images


Now, by curl calls or REST calls, you can create/delete/query a VM, and also attach Storage Block devies to it by:
<h3>
Creating a VM:
</h3>

-> http://localhost:5000/vm/create?name=test_vm&instance_type=type

<h3>
Quering a VM:
</h3>

-> http://localhost:5000/vm/query?vmid=vmid

<h3>
Destroy a VM:
</h3>

-> http://localhost:5000/vm/destroy?vmid=vmid

<h3>
List VM types:
</h3>

-> http://localhost:5000/vm/types

<h3>
Create a Volume Block Storage:
</h3>

-> http://localhost:5000/volume/create?name=test­volume&size=10

<h3>
Query a Volume Block Storage:
</h3>

-> http://localhost:5000/volume/query?volumeid=volumeid

<h3>
Destroy a Volume Block Storage:
</h3>

-> http://localhost:5000/volume/destroy?volumeid=volumeid

<h3>
Attach a Block Storage Device:
</h3>
-> http://localhost:5000/volume/attach?vmid=vmid&volumeid=volumeid

<h3>
Detach a Block Storage Device:
</h3>

-> http://localhost:5000/volume/detach?volumeid=volumeid
