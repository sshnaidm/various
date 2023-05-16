#!/usr/bin/env bash
# this is a first test
# this is a second one
# the third one hsh
# tjrtktjktj

wget http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img
openstack image create cirros_alt --public --container-format=bare --disk-format=qcow2 --property hypervisor_type=kvm --file cirros-0.3.4-x86_64-disk.img
openstack image create cirros --public --container-format=bare --disk-format=qcow2 --property hypervisor_type=kvm --file cirros-0.3.4-x86_64-disk.img

export FLOATING_IP_CIDR=${FLOATING_IP_CIDR:-"192.0.2.0/24"};
export FLOATING_IP_START=${FLOATING_IP_START:-"192.0.2.50"};
export FLOATING_IP_END=${FLOATING_IP_END:-"192.0.2.64"};
export EXTERNAL_NETWORK_GATEWAY=${EXTERNAL_NETWORK_GATEWAY:-"192.0.2.1"};
neutron net-create nova --shared --router:external=True --provider:network_type flat --provider:physical_network datacentre;
neutron subnet-create --name ext-subnet --allocation-pool start=$FLOATING_IP_START,end=$FLOATING_IP_END --disable-dhcp --gateway $EXTERNAL_NETWORK_GATEWAY nova $FLOATING_IP_CIDR;

# Create router
# neutron router-create router1
# neutron router-gateway-set router1 nova

# Create flavors
# nova flavor-create m1.micro 84 128 0 1
# nova flavor-create m1.nano 42 64 0 1


cat<<EOF >/tmp/hieradata/hiera.yaml
---
:backends:
  - yaml
:yaml:
  :datadir: /tmp/hieradata/
:hierarchy:
  - common
EOF

cat<<EOF >/tmp/hieradata/common.yaml
---
tempest::image_name: "cirros"
tempest::image_name_alt: "cirros_alt"
tempest::admin_tenant_name : $OS_TENANT_NAME
tempest::admin_username: $OS_USERNAME
tempest::admin_password: $OS_PASSWORD
tempest::identity_uri: $OS_AUTH_URL
tempest::identity_uri_v3: ${OS_AUTH_URL%/*}/v3
tempest::public_network_name: nova
EOF

#puppet apply $PUPPET_ARGS --modulepath=/etc/puppet/modules --hiera_config=/tmp/hieradata/hiera.yaml -e "include ::tempest" | tee puppet_tempest.log
#CONTROLLER=$(grep -Eo "/[0-9\.]+" ${HOME}/overcloudrc | tr -d "/")
#mkdir -p ${HOME}/contr_hiera/
#ssh -tt heat-admin@${CONTROLLER} "sudo chown heat-admin -R /etc/puppet"
#scp -r heat-admin@${CONTROLLER}:/etc/puppet/hieradata contr_hiera/
#scp -r heat-admin@${CONTROLLER}:/etc/puppet/hiera.yaml contr_hiera/
#sed -i "s%/etc/puppet/hieradata%${HOME}/contr_hiera/hieradata%g" contr_hiera/hiera.yaml

custom_provision_module_path=/home/stack/testt
CONTROLLER=$(grep -Eo "/[0-9\.]+" /home/stack/overcloudrc | tr -d "/")
SSHOPS="-t -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /home/stack/.ssh/id_rsa"
SCPOPS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /home/stack/.ssh/id_rsa"

scp -r $SCPOPS $custom_provision_module_path heat-admin@${CONTROLLER}:~/
ssh $SSHOPS << EOF
sudo mv ~/testt /etc/puppet/modules/
sudo puppet apply --verbose --debug --detailed-exitcodes -e "include ::testt" | tee ~/puppet_run.log
EOF
scp $SCPOPS -r heat-admin@$CONTROLLER:/tmp/openstack /tmp/
