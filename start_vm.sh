#!/bin/bash
set -e
CURDIR=$HOME/virtual
NAME=$1
if [[ -z "${NAME:-}" ]]; then
        echo "Provide name for VM"
        exit 1
fi
IMGS=$HOME/vm_images/
IMAGE=$2
if [[ -z "${IMAGE:-}" || ! -e "$IMAGE" ]]; then
        echo "Please provide path to image to use"
        exit 1
fi

USER_DATA=user-data
META_DATA=meta-data
CI_ISO=${NAME}-cidata.iso

pushd $CURDIR
echo "instance-id: $NAME; local-hostname: $NAME" > $META_DATA
cat <<EOF >user-data
#cloud-config
## Hostname management
preserve_hostname: False
hostname: $NAME
fqdn: ${NAME}.local
#
users:
  - name: stack
    lock_passwd: false
    passwd: '\$1\$sqq40RE/\$uxkZ/2iZBSG0xe89hwsY9/'
    ssh-authorized-keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDhi/BqsZibuAPiUjJe7b3Dqe5nyI7BckOwfGwJYg436+bFQMoR/7RKmtPe+ISVQ04lwIriIPwKGaSHj5mbEe4LsCLZ5jAUHxvWfgHitqS5ln295zU7vp1z28o7e6LQNplgExyqQlxUPdOU48tmlz93F6szSYkNYvZnhzMn9syrajC74qPuKsmHTeYFLEcxesb7/u+BtxCk8WdjYTb//sk038NEtIsNhrGtAOV3WcDpXnA5mNMpUfeoQ4yiN9LqtreXr7Zeo587LV3T2QL+huAE0J7EuCzHAKk6TIzJqjLidg0SYwZZwfbxgviU66QLkeyzh9oiovwskelvOQCBFq3 sshnaidm@sshnaidm.remote.csb.new
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCs0QGs45I+Ha3icMdffJrBKOLgOUISK9CzNp9j6HYs9CAc0lcX9aZVL+J0FSiO5EyBeGzyL22Z5xDWbaQTUQ1of/qQyS7FXK34noJesW+0os1K37Db3JCxyWcgIsNSec3YdbGtPQqHI7YKRYUwYWHYF2AHxe/cOclyYPphnGRa1HgE6dZ7/iHhBRP3XD7zkQUw6tZQ1uxj4QV933QOQlYeB5NjQ7ogb/JTl0Vgx4fM6oRtujklAPykPS4SoDVtnkXnDrL6NDx6ubokJ6nYeQcHgXbQnBNBZ5QkoiAiN6QlDBr+i08gKPSQxMMFYuBa5RbH82sx7OKNcz131RrvhoBf root@dell.tlv
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDAuztyn7xlRSCAu5maP2vPCUgVUugQ6V4GdbknPFugXMFbuvcgmj3B8BfK16gJAEQJhDxb1BCmoBvAf9quD84SbaC3l4iWwMALELEVZCFPsMrC7+la7oUy1ntFXoEYRaZYQvly2f6iPjhU3vUGytxxvtafbZg6PtTbeITyt604jGLoLgsJuNjK8G0DJ0W5/wHVwJGNEcZMgmt9zeFKfELbL2hTJfUd5Fv8p6yFlCLE6ZXwpjAM/W7AvqSB4ttwy4XVOWBd5uePsYiwfdeHWCiMCXzz5VyXv6wluOpZdXT2MDjClzvpO4YTArvK0v1MfWxIQSVmzz/U8DWjFAmENvv1 stack@dell.tlv
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    groups: sudo
    shell: /bin/bash
runcmd:
  - echo '127.0.0.1  ${NAME}.local $NAME' | sudo tee -a /etc/hosts
#ssh_pwauth: True
lock_passwd: false
passwd: '\$1\$sqq40RE/\$uxkZ/2iZBSG0xe89hwsY9/'
chpasswd:
  expire: False
EOF

set +e
virsh --connect qemu:///system destroy "$NAME"
virsh -c qemu:///system snapshot-list ${NAME} --name |while read s; do virsh  --connect qemu:///system snapshot-delete ${NAME} "$s"; done
virsh --connect qemu:///system undefine "$NAME" --remove-all-storage
sleep 2

set -e
genisoimage -output $CI_ISO -volid cidata -joliet -r $USER_DATA $META_DATA &> $NAME.log || {
echo "Failed to create iso file";
exit 1
}
rm -rf "$IMGS/${NAME}.qcow2"
rm -rf "${IMGS_DIR}/${NAME}-2.qcow2"
qemu-img create -f qcow2 -b $IMAGE "$IMGS/${NAME}.qcow2" 80G
#qemu-img create -f qcow2 -o preallocation=metadata "$IMGS/${NAME}.qcow2" 80G
qemu-img create -f qcow2 -o preallocation=metadata "${IMGS}/${NAME}-2.qcow2" 50G
ls $CURDIR/$CI_ISO
virt-install --hvm \
        --import \
        --connect qemu:///system \
        --network bridge:br0 \
        --graphics none \
        --name "${NAME}" \
        --ram=2048 \
        --vcpus=2 \
        --os-type=linux \
        --disk path=$IMGS/${NAME}.qcow2 \
        --disk path=$IMGS/${NAME}-2.qcow2 \
        --disk $CURDIR/$CI_ISO,device=cdrom \
        --cpu host \
        --noautoconsole

popd
virsh --connect qemu:///system console $NAME
