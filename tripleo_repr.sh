#!/bin/bash


#    set environment on fedora(?) machine
#    read abtest-environments/net-iso.yamlout it in tripleo-ci/docs/TripleO-ci.rst
#
#    In toci_gate_test.sh script:
#
#    cleaning yum
#    set env for repository mirrors - epel, fedora, centos
#    set env for node count, introspection, pacemaker(?)
#    set env for overcloud_deploy timeout, overcloud_deploy args - with swap partitions
#    set env for netiso_V4 (network isolation)
#    installing dstat and running it in background
#
#    parsing job name and setting environments based on it
#    adding iptables rules for allowing traffic to be forwarded via instack machine
#
#    In toci-instack.sh script
#
#    set env for stable release - liberty, mitaka, etc
#    set up delorean
#    if no zuul changes - create dummy local repo
#    if changes are about puppet modules or tripleo-ci - don't build anything, puppet will be taken from sources
#    if changes are of something else - build projects with delorean within the local repo
#    run python simple http server to serve this local repo (I use "file repo" in my scripts)
#    set local repo file and set it priority to "1", so that packages from it will be prefferred over others.
#    cleaning yum and removing all packages which were installed from any delorean repos
#
#    set envs DIB_REPOREF and DIB_REPOLOCATION for puppet sources to cloned ones with patches
#    creating undercloud image with disk-image-builder
#    starting undercloud virtual machine
#
#    In deploy.sh script
#
#    On undercloud machine:
#    copying repository files, and environment variables file to undercloud machine
#    installing undercloud there (with tripleo.sh)
#    configuring network isolation (if set to true)
#    creating overcloud images (with tripleo.sh)
#    registering nodes (with tripleo.sh)
#    introspection (if set to true - usually only on non-HA jobs) (with tripleo.sh)
#    deleteing and recreating "baremetal" flavor with 1G swap, 4G memory, 39G disk.
#    deploying overcloud (with tripleo.sh)
#    in HA jobs - wait for heat-api and heat-engine to be available (180 seconds)
#    running pingtest (with tripleo.sh) - creating vm on overcloud with floating IP and ping it



function global_export() {
    local com=$1
    echo "$com" >> ~/envariables
}

function register_job_type() {
    local job_type="$1";

    case $job_type in
        nonha)
            global_export "export INTROSPECT=1"
            global_export 'export NODECOUNT=3'
            global_export 'export OVERCLOUD_DEPLOY_ARGS="$OVERCLOUD_DEPLOY_ARGS -e $TRIPLEO_ROOT/tripleo-ci/test-environments/enable-tls.yaml -e $TRIPLEO_ROOT/tripleo-ci/test-environments/inject-trust-anchor.yaml --ceph-storage-scale 1 -e /usr/share/openstack-tripleo-heat-templates/environments/puppet-ceph-devel.yaml"'
            ;;
        ha)
            global_export "export NETISO_V4=1"
            global_export "export NODECOUNT=4"
            global_export "export PACEMAKER=1"
            #global_export 'export OVERCLOUD_DEPLOY_ARGS="$OVERCLOUD_DEPLOY_ARGS --control-scale 3 --ntp-server 0.centos.pool.ntp.org -e /usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml -e /usr/share/openstack-tripleo-heat-templates/environments/network-isolation.yaml -e /usr/share/openstack-tripleo-heat-templates/environments/net-multiple-nics.yaml -e $TRIPLEO_ROOT/tripleo-ci/test-environments/net-iso.yaml"'
            global_export 'export OVERCLOUD_DEPLOY_ARGS="$OVERCLOUD_DEPLOY_ARGS --control-scale 3 --ntp-server 0.centos.pool.ntp.org -e /usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml"'
            ;;
        containers)
            global_export 'export TRIPLEO_SH_ARGS="--use-containers"'
            ;;
        periodic)
            global_export 'export DELOREAN_REPO_URL=http://trunk.rdoproject.org/centos7/consistent'
            global_export 'export CACHEUPLOAD=1'
            ;;
        liberty|mitaka)
            # This is handled in tripleo.sh (it always uses centos7-liberty/current)
            global_export 'unset DELOREAN_REPO_URL'
            ;;
        upgrades)
            global_export 'export NETISO_V6=1'
            global_export 'export NODECOUNT=3'
            global_export "export PACEMAKER=1"
            global_export 'export OVERCLOUD_DEPLOY_ARGS="$OVERCLOUD_DEPLOY_ARGS -e /usr/share/openstack-tripleo-heat-templates/environments/puppet-pacemaker.yaml --ceph-storage-scale 1"'
            global_export 'export OVERCLOUD_UPDATE_ARGS="-e /usr/share/openstack-tripleo-heat-templates/overcloud-resource-registry-puppet.yaml $OVERCLOUD_DEPLOY_ARGS"'
            ;;
        *)
            echo "Unknown job type:" $job_type
            exit 1
    esac
}

function create_or_check_running_user() {
    useradd stack 2>/dev/null && {
    echo 'stack:qum5net'|chpasswd
    echo "stack ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/stack
    chmod 0440 /etc/sudoers.d/stack
    su - stack && exit
    } || echo "User stack already exists"

    if [[ $(whoami) == "root" ]]; then
        echo "run me as stack user"
        exit
    fi
}

function get_delorean_repos_from_logs() {
    local logdir="$1"

    mkdir -p ~/delorean_repos/

    wget $logdir/logs/undercloud.tar.xz -O undercloud.tar.xz || {
    echo "Can not download $logdir/logs/undercloud.tar.xz"
    exit
    }

    tar -xvJf undercloud.tar.xz
    mv etc/yum.repos.d/delorean* ~/delorean_repos/
    rm -f ~/delorean_repos/delorean-ci.repo
    rm -rf etc/ var/ undercloud.tar.xz
}

function prepare_git_for_cloning() {
    git config --global user.email "stack@tripleo.com"
    git config --global user.name "Stack Test"
}

function clone_repos() {
	local rootdir="$1"
	local zuul="$2"
	if [[ -d "$rootdir" ]]; then
		rm -rf "$rootdir"
	fi
	mkdir -p "$rootdir"
	pushd "$rootdir"
	for pref in $(echo $zuul | tr '^' ' ' | tr -d '"' ); do
		proj=${pref%%:*};
		refs=${pref##*:};
		short_proj=$(basename $proj);
		if [[ -d "$rootdir/$short_proj" ]]; then
			cd "$rootdir/$short_proj"
			git fetch "https://review.openstack.org/${proj}" "$refs" && git cherry-pick FETCH_HEAD || {
			echo "SCRIPT ERROR: Can not merge patch $refs in $proj!"
			exit
			}
		    cd -
		else
			git clone https://review.openstack.org/$proj $rootdir/$short_proj && cd $rootdir/$short_proj && git fetch https://review.openstack.org/$proj $refs && git checkout FETCH_HEAD
		fi
	done
	popd
}

function handle_puppet_repos() {
    local rootdir="$1"

    # handling puppet modules
    for PROJDIR in $rootdir/puppet-*; do
        if [[ -d "$PROJDIR" ]]; then
            REV=$(git --git-dir=$PROJDIR/.git rev-parse HEAD)
            X=${PROJDIR//-/_}
            PROJ=${X##*/}
            echo "export DIB_REPOREF_$PROJ=$REV" >> $rootdir/puppet.env
            echo "export DIB_REPOLOCATION_$PROJ=$PROJDIR" >> $rootdir/puppet.env
        fi
    done
}

function handle_tripleo_ci_repo() {
    local rootdir="$1"
	local zuul="$2"

    mkdir -p "$rootdir" ||:
    rm -rf $rootdir/tripleo-ci
    git clone $TRIPLEOCI_REPO $rootdir/tripleo-ci
    if [[ "$zuul" =~ "tripleo-ci" ]]; then
        refs=$(echo $ZUUL_CHANGES | grep -Eo "tripleo-ci[:0-9/a-z]*" | awk -F":" {'print $NF'})
        pushd $rootdir/tripleo-ci
        git fetch $TRIPLEOCI_REPO $refs && git cherry-pick FETCH_HEAD
        popd
    fi
}

function create_local_delorean_repo() {
    local loc_repo="$1"

    rm -f ~/delorean_repos/delorean-ci.repo
    if [[ -d "$loc_repo" ]]; then
        cat<<EOF > ~/delorean_repos/delorean-ci.repo
[delorean-ci]
name=delorean-ci-local-repo
baseurl=file://${loc_repo}
enabled=1
gpgcheck=0
priority=1
EOF
    else
        echo "WARNING: current local repo is not here! $loc_repo"
    fi
}

function set_up_delorean_repositories() {
    sudo rm -rf /etc/yum.repos.d/*delorean*
    sudo cp -r ~/delorean_repos/*.repo /etc/yum.repos.d/
    sudo yum clean all
    sudo yum repolist
}

function clean(){
    sudo rm -rf /root/.cache
    sudo rm -rf /etc/yum.repos.d/delorean-ci.repo
    # Remove everything installed from a delorean repository (only requred if ci nodes are being reused)
    TOBEREMOVED=$(yumdb search from_repo "*delorean*" | grep -v -e from_repo -e "Loaded plugins" || true)
    [ "$TOBEREMOVED" != "" ] &&  sudo yum remove -y $TOBEREMOVED
    sudo yum clean all
    virsh destroy instack || true
    virsh undefine instack --remove-all-storage || true
    for i in $(virsh list --all --name | grep baremetalbrbm_ ) ; do
        virsh destroy ${i} || true
        virsh undefine ${i} --remove-all-storage || true
    done
    rm -rf ~/delorean_repos
    rm -rf $TRIPLEO_ROOT
    rm -f reproduce.sh

}

#############################################################################
echo "Starting ..............................."
rm -f ~/envariables

export TRIPLEOCI_REPO=https://review.openstack.org/openstack-infra/tripleo-ci
export PERIODICAL=false
global_export 'export PERIODICAL=false'

if [[ -z "$1" ]]; then
    echo "Provide link to build or link to logs as argument"
    exit
elif [[ "$1" =~ "logs.openstack.org" ]]; then
    LOGDIR=$1
elif [[ "$1" =~ "jenkins" ]]; then
    log_path=$(wget -q --no-check-certificate -O - $1"/api/json?pretty=true" | grep '"LOG_PATH"' -A 1 | grep value | awk {'print $NF'} | tr -d '"')
    LOGDIR=http://logs.openstack.org/$log_path
else
    echo "Provide link to build or link to logs as argument or it will run as periodical"
    export JOB_TYPE=${1:-nonha}
    export PERIODICAL=true
    global_export 'export PERIODICAL=true'
    global_export 'export DELOREAN_REPO_URL=http://trunk.rdoproject.org/centos7/consistent'
    global_export 'export CACHEUPLOAD=1'

fi

export TRIPLEO_ROOT=/home/stack/tripleo
export NODE_COUNT=2

global_export 'export EPEL_MIRROR=http://dl.fedoraproject.org/pub/epel'
global_export 'export CENTOS_MIRROR=http://mirror.centos.org/centos'
global_export 'export FEDORA_MIRROR=http://dl.fedoraproject.org/pub/fedora/linux'
global_export 'export NODECOUNT=2'
global_export 'export INTROSPECT=0'
global_export 'export PACEMAKER=0'
global_export 'export OVERCLOUD_DEPLOY_ARGS="--libvirt-type=qemu"'
global_export 'export TRIPLEO_SH_ARGS='
global_export 'export NETISO_V4=0'

JOB_TYPE=${JOB_TYPE:-"$(echo $LOGDIR | grep -Po "\-tripleo-ci[^/]*" | cut -d"-" -f5)"}
echo "Job type = $JOB_TYPE"
register_job_type $JOB_TYPE

if [[ "$JOB_TYPE" != "ha" ]]; then
    export NODE_COUNT=3
    export NODE_CPU=4
    export NODE_MEM=12288
    export UNDERCLOUD_NODE_CPU=4
    export UNDERCLOUD_NODE_MEM=16384
    global_export "export NODE_CPU=4"
    global_export "export NODE_MEM=12288"
    global_export "export UNDERCLOUD_NODE_CPU=4"
    global_export "export UNDERCLOUD_NODE_MEM=16384"
else
    export NODE_COUNT=4
    export NODE_CPU=2
    export NODE_MEM=8192
    export UNDERCLOUD_NODE_CPU=4
    export UNDERCLOUD_NODE_MEM=8192
    global_export "export NODE_CPU=2"
    global_export "export NODE_MEM=8192"
    global_export "export UNDERCLOUD_NODE_CPU=4"
    global_export "export UNDERCLOUD_NODE_MEM=8192"
fi


create_or_check_running_user
clean || :

sudo yum install -y epel-release
sudo yum install -y vim git wget gcc screen yum-plugin-priorities

if ! $PERIODICAL; then

    prepare_git_for_cloning
    get_delorean_repos_from_logs $LOGDIR

    wget $LOGDIR/logs/reproduce.sh -O reproduce.sh
    source <(grep ZUUL_CHANGES= reproduce.sh)
    source <(grep ZUUL_BRANCH= reproduce.sh)
    if [[ "$ZUUL_BRANCH" =~ "stable" ]]; then
        export STABLE_RELEASE=${ZUUL_BRANCH##*/};
        global_export "export STABLE_RELEASE=$STABLE_RELEASE";
        echo "Stable release: $STABLE_RELEASE";
    fi
    DELOREAN_BUILDS=$(echo $ZUUL_CHANGES | tr "^" " ")

    clone_repos "$TRIPLEO_ROOT" "$ZUUL_CHANGES"
    handle_puppet_repos "$TRIPLEO_ROOT"
    handle_tripleo_ci_repo "$TRIPLEO_ROOT" "$ZUUL_CHANGES"

    bash $TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --delorean-setup
    bash $TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --delorean-build "$DELOREAN_BUILDS"
    bash $TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --repo-setup

    local_repo="${TRIPLEO_ROOT}/delorean/data/repos/current"
    create_local_delorean_repo $local_repo
    set_up_delorean_repositories

else
    mkdir -p  $TRIPLEO_ROOT
    handle_tripleo_ci_repo "$TRIPLEO_ROOT"
    bash $TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --repo-setup

fi
sudo hostname $(cat /etc/hostname)
cp ~/envariables $TRIPLEO_ROOT/envariables
sudo yum install -y instack-undercloud

cat<<xxEOFxx > script_2run.sh
#!/bin/sh
cd
sudo yum install -y vim git wget gcc screen yum-plugin-priorities

export TRIPLEO_ROOT=~/tripleo
source \$TRIPLEO_ROOT/envariables || echo "No job types in \$TRIPLEO_ROOT/envariables"
source \$TRIPLEO_ROOT/puppet.env || echo "No puppet env file in \$TRIPLEO_ROOT/puppet.env"

bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --repo-setup

if ! \$PERIODICAL; then
sudo rm -rf /etc/yum.repos.d/*delorean*
sudo cp -r ~/delorean_repos/*.repo /etc/yum.repos.d/
fi
sudo yum clean all
sudo yum repolist

cat > /tmp/deploy_env.yaml << EOENV
parameter_defaults:
  ConfigDebug: true
EOENV

# Install our test cert so SSL tests work
cp \$TRIPLEO_ROOT/tripleo-ci/test-environments/overcloud-cacert.pem /etc/pki/ca-trust/source/anchors/
update-ca-trust extract

export OVERCLOUD_DEPLOY_ARGS="\$OVERCLOUD_DEPLOY_ARGS -e /tmp/deploy_env.yaml"

bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --undercloud

##### Set up networks
#
#if [ \$NETISO_V4 -eq 1 ] || [ \$NETISO_V6 -eq 1 ]; then
#
#    # Update our floating range to use a 10. /24
#    export FLOATING_IP_CIDR=\${FLOATING_IP_CIDR:-"10.0.0.0/24"}
#    export FLOATING_IP_START=\${FLOATING_IP_START:-"10.0.0.100"}
#    export FLOATING_IP_END=\${FLOATING_IP_END:-"10.0.0.200"}
#    export EXTERNAL_NETWORK_GATEWAY=\${EXTERNAL_NETWORK_GATEWAY:-"10.0.0.1"}
#
## Make our undercloud act as the external gateway
## eth6 should line up with the "external" network port per the
## tripleo-heat-template/network/config/multiple-nics templates.
## NOTE: seed uses eth0 for the local network.
#    cat >> /tmp/eth6.cfg <<EOF_CAT
#network_config:
#    - type: interface
#      name: eth6
#      use_dhcp: false
#      addresses:
#        - ip_netmask: 10.0.0.1/24
#EOF_CAT
#    if [ \$NETISO_V6 -eq 1 ]; then
#        cat >> /tmp/eth6.cfg <<EOF_CAT
#        - ip_netmask: 2001:db8:fd00:1000::1/64
#EOF_CAT
#    fi
#    sudo os-net-config -c /tmp/eth6.cfg -v
#fi

######### Continue with scripts

bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --overcloud-images
bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --register-nodes
bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --introspect-nodes


if [[ \$NODE_MEM == '4096' ]]; then
    echo "Recreate the baremetal flavor to add a swap partition"
    source stackrc
    nova flavor-delete baremetal
    nova flavor-create --swap 1024 baremetal auto 4096 39 1
    nova flavor-key baremetal set capabilities:boot_option=local
    export OVERCLOUD_DEPLOY_ARGS="\$OVERCLOUD_DEPLOY_ARGS -e \$TRIPLEO_ROOT/tripleo-ci/test-environments/swap-partition.yaml"
fi
echo "Overcloud deploy args: \$OVERCLOUD_DEPLOY_ARGS"
bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --overcloud-deploy

if [ -n "\${OVERCLOUD_UPDATE_ARGS:-}" ] ; then
    export OVERCLOUD_UPDATE_ARGS="\$OVERCLOUD_UPDATE_ARGS -e \$TRIPLEO_ROOT/tripleo-ci/test-environments/worker-config.yaml"
    bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --overcloud-update \${TRIPLEO_SH_ARGS:-}
fi


OVERCLOUD_PINGTEST_OLD_HEATCLIENT=0 bash \$TRIPLEO_ROOT/tripleo-ci/scripts/tripleo.sh --overcloud-pingtest
xxEOFxx

SEED_IP=$(instack-virt-setup | tee instack_log | grep "^instack vm IP address is " | awk {'print $NF'})
sleep 60
ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@$SEED_IP "cp -r /root/.ssh /home/stack/; chown stack:stack -R /home/stack/.ssh; chmod 744 -R /home/stack/.ssh"

scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no script_2run*.sh stack@$SEED_IP:~/
rsync -zavr -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" ~/delorean_repos stack@$SEED_IP:~/ ||:
rsync -zavr -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" ~/tripleo stack@$SEED_IP:~/
ssh -t -t -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no stack@$SEED_IP "sudo yum install -y screen"
ssh -t -t -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no stack@$SEED_IP "TERM=screen screen -mL bash -c 'bash ~/script_2run.sh 2>&1 | tee local.log'"
