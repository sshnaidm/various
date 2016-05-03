import re

# Patterns regexps
timeout_re = re.compile(r"Killed\s+timeout -s 9 ")
puppet_re = re.compile(r"\"deploy_stderr\": \".+?1;31mError: .+?\W(\w+)::")
resolving_re = re.compile(
    r"Could not resolve host: (\S+); Name or service not known")
exec_re = re.compile(r"mError: (\S+?) \S+ returned 1 instead of one of")
failed_deps_re = re.compile(r"Failed to build (.*)")
curl_re = re.compile(r"curl: \S*? couldn't open file \"(.*?)\"")

PATTERNS = {

    "/console.html": [

        {
            "pattern": "Stack overcloud CREATE_COMPLETE",
            "msg": "Overcloud stack installation: SUCCESS.",
            "tag": "",
        },
        {
            "pattern": "Stack overcloud CREATE_FAILED",
            "msg": "Overcloud stack: FAILED.",
            "tag": "code",
        },
        {
            "pattern": "No valid host was found. There are not enough hosts",
            "msg": "No valid host was found.",
            "tag": "code",
        },
        {
            "pattern": "Failed to connect to trunk.rdoproject.org port 80",
            "msg": "Connection failure to trunk.rdoproject.org.",
            "tag": "infra",
        },
        {
            "pattern": "Overloud pingtest, FAIL",
            "msg": "Overcloud pingtest FAILED.",
            "tag": "code",
        },
        {
            "pattern": "Overcloud pingtest, failed",
            "msg": "Overcloud pingtest FAILED.",
            "tag": "code",
        },
        {
            "pattern": "Error contacting Ironic server: Node ",
            "msg": "Ironic introspection FAIL.",
            "tag": "code",
        },
        {
            "pattern": "Introspection completed with errors:",
            "msg": "Ironic introspection FAIL.",
            "tag": "code",
        },
        {
            "pattern": ": Introspection timeout",
            "msg": "Introspection timeout.",
            "tag": "code",
        },
        {
            "pattern": "is locked by host localhost.localdomain, please retry",
            "msg": "Ironic: Host locking error.",
            "tag": "code",
        },
        {
            "pattern": "Timed out waiting for node ",
            "msg": "Ironic node register FAIL: timeout for node.",
            "tag": "code",
        },
        {
            "pattern": "Killed                  ./testenv-client -b",
            "msg": "Job was killed by testenv-client. Timeout??",
            "tag": "infra",
        },
        {
            "pattern": timeout_re,
            "msg": "Killed by timeout.",
            "tag": "infra",
        },
        {
            "pattern": puppet_re,
            "msg": "Puppet {} FAIL.",
            "tag": "code",
        },
        {
            "pattern": exec_re,
            "msg": "Program {} FAIL.",
            "tag": "code",
        },
        {
            "pattern": "ERROR:dlrn:cmd failed. See logs at",
            "msg": "Delorean FAIL.",
            "tag": "code",
        },
        {
            "pattern": "500 Internal Server Error: Failed to upload image",
            "msg": "Glance upload FAIL.",
            "tag": "code",
        },
        {
            "pattern": "Slave went offline during the build",
            "msg": "Jenkins slave FAIL.",
            "tag": "infra",
        },
        {
            "pattern": resolving_re,
            "msg": "DNS resolve of {} FAIL.",
            "tag": "infra",
        },
        {
            "pattern": "fatal: The remote end hung up unexpectedly",
            "msg": "Git clone repo FAIL.",
            "tag": "infra",
        },
        {
            "pattern": "Create timed out       | CREATE_FAILED",
            "msg": "Create timed out.",
            "tag": "code",
        },
        {
            "pattern": "[overcloud]: CREATE_FAILED Create timed out",
            "msg": "Create timed out.",
            "tag": "code",
        },
        {
            "pattern": "FATAL: no longer a configured node for ",
            "msg": "Slave FAIL: no longer a configured node",
            "tag": "infra",
        },
        {
            "pattern": ("cd: /opt/stack/new/delorean/data/repos: "
                        "No such file or directory"),
            "msg": "Delorean repo build FAIL.",
            "tag": "code",
        },
        {
            "pattern": ("[ERROR] - SEVERE ERROR occurs: "
                        "java.lang.InterruptedException"),
            "msg": "Jenkins lave FAIL: InterruptedException",
            "tag": "infra",
        },
        {
            "pattern": ("Killed                  bash -xe "
                        "/opt/stack/new/tripleo-ci/toci_gate_test.sh"),
            "msg": "Main script timeout",
            "tag": "infra",
        },
        {
            "pattern": ("Command 'instack-install-undercloud' "
                        "returned non-zero exit status"),
            "msg": "Undercloud install FAIL.",
            "tag": "code",
        },
        {
            "pattern": failed_deps_re,
            "msg": "Failed to build dep {}.",
            "tag": "infra",
        },
        {
            "pattern": curl_re,
            "msg": "Failed to upload/get image: {}.",
            "tag": "infra"
        },
        {
            "pattern": "error: command 'gcc' failed with exit status 1",
            "msg": "Failed to compile deps.",
            "tag": "infra"
        },
    ],

    '/logs/postci.txt.gz': [
        {
            "pattern": puppet_re,
            "msg": "Puppet {} FAIL.",
            "tag": "code",
        },
    ],
    # '/logs/overcloud-controller-0.tar.xz//var/log/neutron/server.log': [
    #     {
    #         "pattern": 'Extension router-service-type not supported',
    #         "msg": "Testing pattern, please ignore.",
    #         "tag": "code",
    #     },
    # ]
}
