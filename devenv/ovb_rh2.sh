#!/bin/bash
TIMEOUT=300
NAME=${1:-"$USER"}
RHCL="2"
JUMPHOST=8.43.87.251

bold=$(tput bold)
normal=$(tput sgr0)

function wait_for_ready_undercloud() {
is_ready=$(nova list | grep ${NAME}-undercloud | grep ACTIVE)
run_timeout=0
while [[ ! "$is_ready" ]] && [[ $run_timeout -lt $TIMEOUT ]] ; do
    is_ready=$(nova list | grep ${NAME}-undercloud | grep ACTIVE)
    sleep 10
    run_timeout=$(($run_timeout + 10))
done
if [[ ! "$is_ready" ]]; then
    echo "Can't build undercloud with nova"
    exit 1
fi
}

function wait_for_deleted_undercloud() {

exists=$(nova list | grep ${NAME}-undercloud)
run_timeout=0
while  [[ "$exists" ]] && [[ $run_timeout -lt $TIMEOUT ]] ; do
    exists=$(nova list | grep ${NAME}-undercloud)
    sleep 10
    run_timeout=$(($run_timeout + 10))
done
if nova list | grep ${NAME}-undercloud; then
    echo "Can't delete the undercloud"
    exit 1
fi
}

function create_script_for_patch {
cat<< EOF >prepare_patch.sh
#!/bin/sh
LOG="\$1"
if [[ -z "\${LOG:-}" ]]; then
    echo "Give me a logs URl"
    exit 1
fi
echo "\${LOG}/logs/reproduce.sh"
wget "\${LOG}/logs/reproduce.sh" -O reproduce_me || exit
PROJ=\$(grep -o 'ZUUL_PROJECT=".*"' reproduce_me | cut -d'"' -f2)
FOLDER=\$(echo \$PROJ | cut -d"/" -f2)
REFS=\$(grep -Eo 'ZUUL_CHANGES=".*"' reproduce_me | cut -d":" -f3 | tr -d '"')
BRANCH=\$(grep -Eo 'ZUUL_BRANCH=".*"' reproduce_me  | head -1 | cut -d'"' -f2)

cd /opt/stack/new
git clone https://git.openstack.org/\${PROJ}
cd \$FOLDER
git fetch https://git.openstack.org/\${PROJ} \$REFS && git checkout FETCH_HEAD
git reset --hard FETCH_HEAD

cd /opt/stack/new/tripleo-ci
sed -i "s/xargs -t/xargs -r -t/" toci_instack_ovb.sh

echo "TE_DATAFILE=/tmp/env.json OVERRIDE_ZUUL_BRANCH=\$BRANCH WORKSPACE=/tmp DEVSTACK_GATE_TIMEOUT=200 ZUUL_BRANCH=\$BRANCH ZUUL_CHANGES="\${PROJ}:\${BRANCH}:\${REFS}" ZUUL_PROJECT=\$PROJ TOCI_JOBTYPE=ovb-ha ./toci_gate_test.sh 2>&1 | tee general.log" > run_me.sh
EOF
chmod a+x prepare_patch.sh
}

function create_script_for_mirrors {
    cat<< EOK >provider
NODEPOOL_PROVIDER=tripleo-test-cloud-rh${RHCL}
NODEPOOL_CLOUD=tripleo-test-cloud-rh${RHCL}
NODEPOOL_REGION=regionOne
NODEPOOL_AZ=
EOK
}

function check_binary {
    local binary="$1"
    command -v "$binary" >/dev/null 2>&1
    if [[ $? != 0 ]]; then
        echo "This script requires ${bold}nova${normal} and ${bold}glance${normal} clients to be installed."
        echo "You need to install $binary client before running this script"
        exit 1
    fi
}

# Destroy everything

source ~/rh${RHCL}devrc || {
echo "Please provide ~/rh${RHCL}devrc with cloud credentials for tripleo-user tenant";
exit 1
}

check_binary nova
check_binary glance

ssh centos@$JUMPHOST -A "./tripleo-ci/scripts/te-broker/destroy-env ${NAME}"
nova delete ${NAME}-undercloud
wait_for_deleted_undercloud

# Start everything

last_image=$(glance image-list --sort-key name | grep template-centos-7 | head -1 | awk {'print $4'})
nova boot --config-drive=true --image ${last_image} --flavor undercloud --nic net-name=private --key-name default ${NAME}-undercloud
wait_for_ready_undercloud

undercloud_uuid=$(nova list --fields "name" | grep ${NAME}-undercloud | awk {'print $2'})
undercloud_ip=$(nova show ${NAME}-undercloud | grep "private network" | awk {'print $5'})

create_script_for_patch
create_script_for_mirrors

echo "TE_DATAFILE=~/testenv.json ./tripleo-ci/scripts/te-broker/create-env ${NAME} 5 $undercloud_uuid"
ssh centos@$JUMPHOST -A "TE_DATAFILE=~/testenv.json ./tripleo-ci/scripts/te-broker/create-env ${NAME} 5 $undercloud_uuid"
ssh -ttt centos@$JUMPHOST -A "sed -i '/$undercloud_ip/'d ~/.ssh/known_hosts"
scp prepare_patch.sh centos@$JUMPHOST:/tmp/
scp provider centos@$JUMPHOST:/tmp/

ssh centos@$JUMPHOST -A <<EOF
ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@$undercloud_ip <<EOZ
mkdir -p /home/jenkins/.ssh ||:
cat /root/.ssh/authorized_keys >> /home/jenkins/.ssh/authorized_keys
chown jenkins:jenkins -R /home/jenkins/.ssh/
chmod 600 /home/jenkins/.ssh/authorized_keys
EOZ

scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ~/testenv.json root@$undercloud_ip:/tmp/env.json;
scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no /tmp/provider root@$undercloud_ip:/etc/nodepool/
scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no /tmp/prepare_patch.sh jenkins@$undercloud_ip:~/
ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@$undercloud_ip <<EOT
su - jenkins
sudo mkdir -p /opt/stack/new ;
sudo chown jenkins -R /opt/stack/new ;
git clone https://git.openstack.org/openstack-infra/tripleo-ci /opt/stack/new/tripleo-ci ;
cd /opt/stack/new/tripleo-ci/ ;
cp ~/prepare_patch.sh . ;

echo "TE_DATAFILE=/tmp/env.json OVERRIDE_ZUUL_BRANCH= ZUUL_BRANCH=master WORKSPACE=/tmp DEVSTACK_GATE_TIMEOUT=200 TOCI_JOBTYPE= ./toci_gate_test.sh | tee general.log" > run_clean.sh
echo "TE_DATAFILE=/tmp/env.json OVERRIDE_ZUUL_BRANCH= ZUUL_BRANCH=master WORKSPACE=/tmp DEVSTACK_GATE_TIMEOUT=200 TOCI_JOBTYPE=periodic-ovb-nonha-test ./toci_gate_test.sh | tee general.log" > run_periodic.sh
EOT
EOF
echo "Connect to centos@$JUMPHOST -A and then to jenkins@$undercloud_ip and run your command"
echo "ssh -ttt centos@$JUMPHOST -A \"ssh -ttt jenkins@$undercloud_ip 'cd /opt/stack/new/tripleo-ci; bash'\" "

