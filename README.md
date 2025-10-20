# hwcert-jenkins-tools

Utility scripts and tools authored by the Certification Team to enhance and automate CI/CD pipelines.

## Downloadable installer

Certification tasks that need to make use of the tools in this repo can use the downloadable installer:

```bash
curl -Ls -o install_tools.sh https://raw.githubusercontent.com/canonical/hwcert-jenkins-tools/main/install_tools.sh
source install_tools.sh tools --branch LM-1580-sru-refactor
```

The installer clones this repo in a readable, consistent manner.
It can also clone from branches, useful in cases where new tools are being developed and tested.

## An overview of available tools

### Elementary actions over ssh

#### Run commands on the device

The `_run` script executes the specified command on the device over SSH.

Examples:
```
_run mkdir /var/tmp/pts-cache
_run sudo reboot
_run sudo add-apt-repository -y ppa:firmware-testing-team/ppa-fwts-stable
_run sudo snap refresh
_run sudo snap install --no-wait $RUNTIME_NAME --channel=$RUNTIME_CHANNEL
_run [ -f /var/snap/docker/current/config/daemon.json ]
_run "snap model --assertion" | sed -n 's/^store:\s\(.*\)$/\1/p'
```

The `_run` script, as well as all other scripts that rely on executing commands
over SSH, rely on the following:
- The `DEVICE_IP` environment variable must be set, in order to specify the IP of the device.
- If the device requires a non-standard username (i.e. different than `ubuntu`) it should specified through the `DEVICE_USER` environment variable.
- If a password is required in order to SSH into the device, it should be specified through the `DEVICE_PWD` environment variable.

#### Transfer files to and from the device

The `_put` and `_get` scripts can transfer files to and from the device over SSH.

Examples:
```
_get /snap/$CHECKBOX_FRONTEND/current/bin/launcher checkbox-launcher
_put certification.gschema.override :
_put "${DEVICE_SCRIPTLETS[@]/#/$SCRIPTLETS_PATH/}" :"$TOOLS_PATH_DEVICE"
```

### Barriers

There are instances where the execution of the testing script needs to be
blocked, waiting for a specific state to be reached before proceeding.

#### Wait for a device to be reachable

The `wait_for_ssh` script exits when the device is up-and-running,
ready to execute commands over SSH.

Internally, the script runs `systemctl is-running` on the device and
it depends on the returned value to determine if the system is ready.
Normally, only the `running` state results in the `wait_for_ssh` script
exiting. If the system is `starting` or `stopping` then `wait_for_ssh`
will keep retrying, so it often follows `_run sudo reboot` in order
to ensure that no further commands are executed until the device is
ready.

The `--allow-degraded` flag can be used in cases where it is acceptable
that the device is in a `degraded` state, due to some services that have
failed to start.

Example:
```
_run sudo reboot
wait_for_ssh --allow-degraded
```

There are default values for the number of retries and the delay between
them but if these aren't appropriate they can be set explicitly through
the `--times` and `--delay` command-line arguments. This applies to all
`wait_` scripts.

#### Wait for all deb installation actions to complete

The `wait_for_packages_complete` script exits when all package operations
(apt, dpkg) are complete. This is useful in cases when background updates
or auto-updates might be running. It is also handy when certain lock files
might remain locked for slightly longer, even though no package operations
are ongoing.

Example:
```
_run wait_for_packages_complete
```

Note that this particular script is executed directly _on the device_
(it is copied over to the device when the installer runs).

#### Wait for all snap changes to complete

The `wait_for_snap_changes` script exits when all snap operations on the
device are complete.

It is suggested that snap operations on the device (like installing or
refreshing snaps) are performed with the `--no-wait` option, followed by
a call to `wait_for_snap_changes`. This ensures stability and reliability
when a snap operation might lead to a reboot or might require a manual
reboot (which the script checks for and performs, when necessary).

Examples:
```
_run sudo snap refresh --no-wait
wait_for_snap_changes
```

### Installing packages

It is suggested that Debian packages are installed on the device using
the `install_packages` script. The script itself can accept these flags:
- `--no-update`: do not perform an update before installation
- `--dist-upgrade`: perform an upgrade instead of installing packages
All other arguments after a `--` are propagated to `apt-get install` and
no `--` is required if there are no script arguments.

Examples:
```
_run install_packages linux-generic
_run install_packages --install-recommends $PACKAGES
_run install_packages --no-update -- checkbox-provider-phoronix libssl1.1
```

Note that this particular script is executed directly _on the device_
(it is copied over to the device when the installer runs).

### Installing Checkbox

Installing Checkbox is typically a non-trivial multi-step process and it
is strongly suggested that the `install_checkbox_debs` and `install_checkbox_snaps`
scripts are used for this purpose.

Examples:
```
install_checkbox_debs stable
install_checkbox_debs beta --providers checkbox-provider-certification-server
install_checkbox_snaps checkbox=latest/beta
install_checkbox_snaps checkbox-shiner=latest/edge --additional checkbox-ce-oem=latest/stable
```

On non-provision machines, it is also hightly recommended that the
`clean_machine` script is used as early as possible:

```
_run clean_machine --im-sure
```

Note that this particular script is executed directly _on the device_
(it is copied over to the device when the installer runs).

## Additional tools

### A "stacker" for Checkbox configuration files

Certification tasks need to assemble several Checkbox configuration files (e.g. a common "head", a test plan, a manifest, environment variables) into a single file, also adding a description to it.

This repo contains `stacker`, a purpose-built Python tool that offers this functionality.

```bash
stacker --output checkbox.conf launcher.conf manifest.conf --description "A description"
```

## What about the rest?

This repo contains additional tools and even more scriptlets.
Some of these are used under the hood by the scripts that are described here.
Others are simply used in other workflows.
However, the scripts in this overview provide the essential functionality
for performing scripted testing.