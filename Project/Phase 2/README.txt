Cloud-Orchestration-Layer
=========================

A Cloud Orchestration Layer: Creating/Deleting/Quering and Scheduling Virtual Machines(VMs) in a given Network

How does it work?

Write the information of the machines in file named: pm_file

And also the Location of the VM image file in file name: image_file

cd bin

./script ../src/pm_file ../src/image_file ../src/flavor_file


Now, by curl calls or REST calls, you can create/delete/query a VM:
<h3>
Creating a VM:
</h3>

-> http://127.0.0.1:5000/vm/create?name=test_vm&instance_type=type&image_id=image_id

<h3>
Quering a VM:
</h3>

-> http://127.0.0.1:5000/vm/query?vmid=vmid

<h3>
Destroy a VM:
</h3>

-> http://127.0.0.1:5000/vm/destroy?vmid=vmid

<h3>
List VM types:
</h3>

-> http://127.0.0.1:5000/vm/types

and many more

Extra Features

Schedular is designed so that there is no load on only one machine
Used Mongo Engine to store all the request and of created virtual machines

Technologies Used

MongoEngine
Flask

