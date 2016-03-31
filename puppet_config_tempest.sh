#!/usr/bin/env bash
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

puppet apply $PUPPET_ARGS --modulepath=/etc/puppet/modules --hiera_config=/tmp/hieradata/hiera.yaml -e "include ::tempest" | tee puppet_tempest.log
