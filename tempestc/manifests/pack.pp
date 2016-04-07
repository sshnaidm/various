class tempest2 {

  # $username             = hiera('CONFIG_PROVISION_TEMPEST_USER')
  # $password             = hiera('CONFIG_PROVISION_TEMPEST_USER_PW')
  # $tenant_name          = 'admin'
  # $floating_range       = hiera('CONFIG_PROVISION_TEMPEST_FLOATRANGE')

  $username             = "admin"
  $password             = "fE69CWdwpvptwaVrJVAyGYtBq"
  $tenant_name          = "admin"
  $floating_range       = "192.0.2.0/24"
  $gateway_ip           = "192.0.2.1"
  $floating_pool        = 'start=192.0.2.50,end=192.0.2.99'

  # Authentication/Keystone
  # $identity_uri          = hiera('CONFIG_KEYSTONE_PUBLIC_URL')
  # $identity_uri_v3       = regsubst($identity_uri, 'v2.0', 'v3')
  # $auth_version          = regsubst(hiera('CONFIG_KEYSTONE_API_VERSION'), '.0', '')
  # $admin_username        = hiera('CONFIG_KEYSTONE_ADMIN_USERNAME')
  # $admin_password        = hiera('CONFIG_KEYSTONE_ADMIN_PW')
  # $admin_tenant_name     = 'admin'
  # $admin_domain_name     = 'Default'

  $identity_uri          = "http://192.0.2.6:5000/v2.0"
  $identity_uri_v3       = regsubst($identity_uri, 'v2.0', 'v3')
  $auth_version          = "2"
  $admin_username        = "admin"
  $admin_password        = "fE69CWdwpvptwaVrJVAyGYtBq"
  $admin_tenant_name     = 'admin'
  $admin_domain_name     = 'Default'

  # get image and network id
  $configure_images          = true
  $configure_networks        = true

  # Image
  # $image_name         = hiera('CONFIG_PROVISION_IMAGE_NAME')
  # $image_ssh_user     = hiera('CONFIG_PROVISION_IMAGE_SSH_USER')
  # $image_name_alt     = "${image_name}_alt"
  # $image_alt_ssh_user = hiera('CONFIG_PROVISION_IMAGE_SSH_USER')
  # $image_source       = hiera('CONFIG_PROVISION_IMAGE_URL')
  # $image_format       = hiera('CONFIG_PROVISION_IMAGE_FORMAT')

  $image_name         = "cirros"
  $image_ssh_user     = "cirros"
  $image_name_alt     = "${image_name}_alt"
  $image_alt_ssh_user = "cirros"
  $image_source       = "http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img"
  $image_format       = "qcow2"

  # network name
  # $public_network_name = 'nova'

  # nova should be able to resize with packstack setup
  $resize_available          = true

  $change_password_available = undef
  $allow_tenant_isolation    = true
  $dir_log                   = "/tmp/"
  $log_file                  = "${dir_log}/tempest.log"
  $use_stderr                = false
  $debug                     = true
  $public_router_id          = undef

  ##########################################################################

  ## Neutron
  $public_network_name  = 'public'
  $public_subnet_name   = 'public_subnet'
  $private_network_name = 'private'
  $private_subnet_name  = 'private_subnet'
  $fixed_range          = '10.0.0.0/24'
  $router_name          = 'router1'

  keystone_tenant { $tenant_name:
    ensure      => present,
    enabled     => true,
    description => 'default tenant',
  }

  keystone_user { $username:
    ensure   => present,
    enabled  => true,
    password => $password,
  }

  if $heat_available {
    keystone_user_role { "${username}@${tenant_name}":
      ensure => present,
      roles  => ['_member_', 'heat_stack_owner'],
    }
  } else {
    keystone_user_role { "${username}@${tenant_name}":
      ensure => present,
      roles  => ['_member_'],
    }
  }

  ## Neutron
  $neutron_deps = [Neutron_network[$public_network_name]]

  neutron_network { $public_network_name:
    ensure          => present,
    router_external => true,
    tenant_name     => $admin_tenant_name,
  }
  neutron_subnet { $public_subnet_name:
    ensure           => 'present',
    cidr             => $floating_range,
    enable_dhcp      => false,
    allocation_pools => [$floating_pool],
    gateway_ip       => $gateway_ip,
    network_name     => $public_network_name,
    tenant_name      => $admin_tenant_name,
  }
  neutron_network { $private_network_name:
    ensure      => present,
    tenant_name => $tenant_name,
  }
  neutron_subnet { $private_subnet_name:
    ensure       => present,
    cidr         => $fixed_range,
    network_name => $private_network_name,
    tenant_name  => $tenant_name,
  }
  # Tenant-owned router - assumes network namespace isolation
  neutron_router { $router_name:
    ensure               => present,
    tenant_name          => $tenant_name,
    gateway_network_name => $public_network_name,
    # A neutron_router resource must explicitly declare a dependency on
    # the first subnet of the gateway network.
    require              => Neutron_subnet[$public_subnet_name],
  }
  neutron_router_interface { "${router_name}:${private_subnet_name}":
    ensure => present,
  }



  # Tempest
  $tempest_repo_uri      = "https://github.com/openstack/tempest.git"
  $tempest_repo_revision = "master"
  $tempest_clone_path    = '/tmp/tempest_repo'
  $tempest_clone_owner   = 'root'
  $setup_venv            = true

  # Service availability for testing based on configuration
  $cinder_available     = true
  $glance_available     = true
  $horizon_available    = false
  $nova_available       = true
  $neutron_available    = true
  $ceilometer_available = false
  $aodh_available       = false
  $trove_available      = false
  $sahara_available     = true
  $heat_available       = true
  $swift_available      = true

  # on standalone install we depend on this package
  package { 'python-openstackclient':
    before => Class['::tempest'],
  }

  class { '::tempest':
    admin_domain_name         => $admin_domain_name,
    admin_password            => $admin_password,
    admin_tenant_name         => $admin_tenant_name,
    admin_username            => $admin_username,
    allow_tenant_isolation    => $allow_tenant_isolation,
    aodh_available            => $aodh_available,
    auth_version              => $auth_version,
    ceilometer_available      => $ceilometer_available,
    cinder_available          => $cinder_available,
    change_password_available => $change_password_available,
    configure_images          => $configure_images,
    configure_networks        => $configure_networks,
    debug                     => $debug,
    glance_available          => $glance_available,
    heat_available            => $heat_available,
    horizon_available         => $horizon_available,
    identity_uri              => $identity_uri,
    identity_uri_v3           => $identity_uri_v3,
    image_alt_ssh_user        => $image_alt_ssh_user,
    image_name_alt            => $image_name_alt,
    image_name                => $image_name,
    image_ssh_user            => $image_ssh_user,
    log_file                  => $log_file,
    neutron_available         => $neutron_available,
    nova_available            => $nova_available,
    password                  => $password,
    public_network_name       => $public_network_name,
    public_router_id          => $public_router_id,
    resize_available          => $resize_available,
    sahara_available          => $sahara_available,
    setup_venv                => $setup_venv,
    swift_available           => $swift_available,
    tempest_clone_owner       => $tempest_clone_owner,
    tempest_clone_path        => $tempest_clone_path,
    tempest_repo_revision     => $tempest_repo_revision,
    tempest_repo_uri          => $tempest_repo_uri,
    tenant_name               => $tenant_name,
    trove_available           => $trove_available,
    username                  => $username,
    use_stderr                => $use_stderr,
  }

  tempest_config { 'object-storage/operator_role':
    value => 'SwiftOperator',
    path  => "${tempest_clone_path}/etc/tempest.conf",
  }

}