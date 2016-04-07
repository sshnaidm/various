# Deploy OpenStack resources needed to run Tempest

# Configure some common parameters
#
# [*ssl*]
#   (optional) Boolean to enable or not SSL.
#   Defaults to false.
#
# [*ipv6*]
#   (optional) Boolean to enable or not IPv6.
#   Defaults to false.
#
class tempestc::config (
  $ssl  = false,
  $ipv6 = false,
) {

  if $ssl {
    $rabbit_port = '5671'
    $proto       = 'https'
  } else {
    $rabbit_port = '5672'
    $proto       = 'http'
  }

  if $ipv6 {
    $host       = '::1'
    $rabbit_env = {
      'RABBITMQ_NODE_IP_ADDRESS'   => $host,
      'RABBITMQ_SERVER_START_ARGS' => '"-proto_dist inet6_tcp"',
    }
    $ip_version  = '6'
  } else {
#    $host        = '127.0.0.1'
    $rabbit_env  = {}
    $ip_version  = '4'
  }

  # in URL, brackets are needed
#  $ip_for_url = normalize_ip_for_uri($host)

#  $base_url           = "${proto}://${ip_for_url}"
  $os_username        = undef
  $os_password        = undef
  $os_tenant_name     = undef
  $os_keystone_url    = undef
  $base_url           = "${os_keystone_url}"
  $keystone_auth_uri  = "${base_url}:5000"
  $keystone_admin_uri = "${base_url}:35357"
}


class tempestc::provision {

  include tempestc::config
  $os_auth_options = "--os-username ${tempestc::config::os_username} --os-password ${tempestc::config::os_password} --os-tenant-name ${tempestc::config::os_tenant_name} --os-auth-url ${tempestc::config::keystone_auth_uri}/v2.0"

  exec { 'manage_m1.nano_nova_flavor':
    path     => '/usr/bin:/bin:/usr/sbin:/sbin',
    provider => shell,
    command  => "nova ${os_auth_options} flavor-create m1.nano 42 128 0 1",
    unless   => "nova ${os_auth_options} flavor-list | grep m1.nano",
  }
#  Keystone_user_role['admin@openstack'] -> Exec['manage_m1.nano_nova_flavor']

  exec { 'manage_m1.micro_nova_flavor':
    path     => '/usr/bin:/bin:/usr/sbin:/sbin',
    provider => shell,
    command  => "nova ${os_auth_options} flavor-create m1.micro 84 128 0 1",
    unless   => "nova ${os_auth_options} flavor-list | grep m1.micro",
  }
#  Keystone_user_role['admin@openstack'] -> Exec['manage_m1.micro_nova_flavor']

  neutron_network { 'public':
    tenant_name     => 'admin',
    router_external => true,
  }
#  Keystone_user_role['admin@openstack'] -> Neutron_network<||>

  neutron_subnet { 'public-subnet':
    cidr             => '172.24.5.0/24',
    ip_version       => '4',
    allocation_pools => ['start=172.24.5.10,end=172.24.5.200'],
    gateway_ip       => '172.24.5.1',
    enable_dhcp      => false,
    network_name     => 'public',
    tenant_name      => 'admin',
  }

  # vs_bridge { 'br-ex':
  #   ensure => present,
  #   notify => Exec['create_loop1_port'],
  # }
  #
  # # create dummy loopback interface to exercise adding a port to a bridge
  # exec { 'create_loop1_port':
  #   path        => '/usr/bin:/bin:/usr/sbin:/sbin',
  #   provider    => shell,
  #   command     => 'ip link add name loop1 type dummy; ip addr add 127.2.0.1/24 dev loop1',
  #   refreshonly => true,
  # }->
  # vs_port { 'loop1':
  #   ensure => present,
  #   bridge => 'br-ex',
  #   notify => Exec['create_br-ex_vif'],
  # }
  #
  # # creates br-ex virtual interface to reach floating-ip network
  # exec { 'create_br-ex_vif':
  #   path        => '/usr/bin:/bin:/usr/sbin:/sbin',
  #   provider    => shell,
  #   command     => 'ip addr add 172.24.5.1/24 dev br-ex; ip link set br-ex up',
  #   refreshonly => true,
  # }

  glance_image { 'cirros':
    ensure           => present,
    container_format => 'bare',
    disk_format      => 'qcow2',
    is_public        => 'yes',
    # TODO(emilien) optimization by 1/ using Hiera to configure Glance image source
    # and 2/ if running in the gate, use /home/jenkins/cache/files/ cirros image.
    # source        => '/home/jenkins/cache/files/cirros-0.3.4-x86_64-disk.img',
    source           => 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img',
  }
  glance_image { 'cirros_alt':
    ensure           => present,
    container_format => 'bare',
    disk_format      => 'qcow2',
    is_public        => 'yes',
    # TODO(emilien) optimization by 1/ using Hiera to configure Glance image source
    # and 2/ if running in the gate, use /home/jenkins/cache/files/ cirros image.
    # source        => '/home/jenkins/cache/files/cirros-0.3.4-x86_64-disk.img',
    source           => 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img',
  }
#  Keystone_user_role['admin@openstack'] -> Glance_image<||>
}
