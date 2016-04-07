class testt::config {
  $os_username = 'admin'
  $os_tenant_name = hiera(keystone::roles::admin::admin_tenant)
  $os_password = hiera(admin_password)
  $os_auth_url = hiera(keystone::endpoint::public_url)
  $keystone_auth_uri = regsubst($os_auth_url, '/v2.0', '')
  $floating_range       = "192.0.2.0/24"
  $gateway_ip           = "192.0.2.1"
  $floating_pool        = 'start=192.0.2.50,end=192.0.2.99'
  $fixed_range          = '10.0.0.0/24'
  $router_name          = 'router1'
  $ca_bundle_cert_path = '/etc/ssl/certs/ca-bundle.crt'
  $cert_path           = '/etc/pki/ca-trust/source/anchors/puppet_openstack.pem'
  $update_ca_certs_cmd = '/usr/bin/update-ca-trust force-enable && /usr/bin/update-ca-trust extract'
  $host_url = regsubst($keystone_auth_uri, ':5000', '')

}


class testt::provision {
  include testt::config

  $os_auth_options = "--os-username ${config::os_username} --os-password ${config::os_password} --os-tenant-name ${config::os_tenant_name} --os-auth-url ${config::os_auth_url}/v2.0"

  exec { 'manage_m1.nano_nova_flavor':
    path     => '/usr/bin:/bin:/usr/sbin:/sbin',
    provider => shell,
    command  => "nova ${os_auth_options} flavor-delete m1.nano ||: ; nova ${os_auth_options} flavor-create m1.nano pup_tempest_custom_nano 128 0 1",
    unless   => "nova ${os_auth_options} flavor-list | grep pup_tempest_custom_nano",
  }

  exec { 'manage_m1.micro_nova_flavor':
    path     => '/usr/bin:/bin:/usr/sbin:/sbin',
    provider => shell,
    command  => "nova ${os_auth_options} flavor-delete m1.micro ||: ;nova ${os_auth_options} flavor-create m1.micro pup_tempest_custom_micro 128 0 1",
    unless   => "nova ${os_auth_options} flavor-list | grep pup_tempest_custom_micro",
  }


  $neutron_deps = [Neutron_network['nova']]

  neutron_network { 'nova':
      ensure          => 'present',
      router_external => true,
      tenant_name     => "${config::os_tenant_name}",
    }

  neutron_subnet { 'ext-subnet':
    ensure           => 'present',
    cidr             => "${config::floating_range}",
    enable_dhcp      => false,
    allocation_pools => ["${config::floating_pool}"],
    gateway_ip       => "${config::gateway_ip}",
    network_name     => 'nova',
    tenant_name      => "${config::os_tenant_name}",
  }

  neutron_network { 'private':
      ensure      => 'present',
      tenant_name => "${config::os_tenant_name}",
    }

  neutron_subnet { 'private_subnet':
    ensure       => 'present',
    cidr         => "${config::fixed_range}",
    network_name => 'private',
    tenant_name  => "${config::os_tenant_name}",
  }
  # Tenant-owned router - assumes network namespace isolation
  neutron_router { "${config::router_name}":
    ensure               => 'present',
    tenant_name          => "${config::os_tenant_name}",
    gateway_network_name => 'nova',
    # A neutron_router resource must explicitly declare a dependency on
    # the first subnet of the gateway network.
    require              => Neutron_subnet['ext-subnet'],
  }
  neutron_router_interface { "${config::router_name}:private_subnet":
    ensure => 'present',
  }

  glance_image { 'cirros':
    ensure           => present,
    container_format => 'bare',
    disk_format      => 'qcow2',
    is_public        => 'yes',
    source           => 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img',
  }
  glance_image { 'cirros_alt':
    ensure           => present,
    container_format => 'bare',
    disk_format      => 'qcow2',
    is_public        => 'yes',
    source           => 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img',
  }

  class { '::tempest':


    debug                  => true,
    use_stderr             => false,
    log_file               => 'tempest.log',
    tempest_clone_owner    => $::id,
    git_clone              => true,
    setup_venv             => true,
    tempest_clone_path     => '/tmp/openstack/tempest',
    lock_path              => '/tmp/openstack/tempest',
    tempest_config_file    => '/tmp/openstack/tempest/etc/tempest.conf',
    configure_images       => true,
    configure_networks     => true,
    allow_tenant_isolation => true,
    identity_uri           => "${testt::config::keystone_auth_uri}/v2.0",
    identity_uri_v3        => "${testt::config::keystone_auth_uri}/v3",
    admin_username         => "${testt::config::os_username}",
    admin_tenant_name      => "${testt::config::os_tenant_name}",
    admin_password         => "${testt::config::os_password}",
    admin_domain_name      => 'Default',
    auth_version           => 'v3',
    image_name             => 'cirros',
    image_name_alt         => 'cirros_alt',
    cinder_available       => true,
    glance_available       => true,
    horizon_available      => $horizon,
    nova_available         => true,
    neutron_available      => true,
    ceilometer_available   => $ceilometer,
    aodh_available         => $aodh,
    trove_available        => $trove,
    sahara_available       => $sahara,
    heat_available         => $heat,
    swift_available        => true,
    ironic_available       => $ironic,
    public_network_name    => 'nova',
    dashboard_url          => "${testt::config::host_url}",
    flavor_ref             => 'pup_tempest_custom_nano',
    flavor_ref_alt         => 'pup_tempest_custom_micro',
    image_ssh_user         => 'cirros',
    image_alt_ssh_user     => 'cirros',
    img_file               => 'cirros-0.3.4-x86_64-disk.img',
    compute_build_interval => 10,
    ca_certificates_file   => "${testt::config::ca_bundle_cert_path}",
    img_dir                => '/tmp/openstack/tempest',
  }

tempest_config { 'object-storage/operator_role':
  value => 'SwiftOperator',
  path  => "${tempest_clone_path}/etc/tempest.conf",
}

}
