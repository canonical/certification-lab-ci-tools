# The Certification `toolbox` package

## Introduction

The `toolbox` package offers Python implementations for a range of tasks
commonly performed within certification testing workflows, such as
testing whether a remote device is accessible, installing deb and snap
packages on a remote device and deploying Checkbox.

It provides a clean, modular, extensible and testable alternative to the
corresponding bash "scriptlets".

## Core Concepts

The `toolbox` package is built around two fundamental abstractions:
_devices_ and _interfaces_.

### Devices

A _device_ represents a machine and is essentially the abstraction that
allows you to run commands on the machine.

There are different types of devices:
- `LocalHost` represents the machine running the script
- `RemoteDevice` represents a remote device where commands can be executed
  over SSH
- `LabDevice` is a remote device configured specifically for access in the
  way Canonical lab devices are accessed (usually through a Testflinger agent)

#### Code Examples

```python
from toolbox.devices import LocalHost
device = LocalHost()
device.run(["uname", "-r"])
```

```python
from toolbox.devices.lab import LabDevice
# the DEVICE_IP environment variable needs to be set
device = LabDevice()
device.run(["uname", "-r"])
```

You can try reserving a lab device through Testflinger and exporting `DEVICE_IP`
to the IP of the machine you have reserved. This piece of code should allow
you to execute commands on the reserved device.

#### Under the hood

The unifying view of "devices" on which commands can be executed is made
possible through the use of the `fabric` package, along with its
dependencies, i.e. `invoke` and `paramiko`.

Running commands locally doesn't directly involve using `subprocess` and
running commands remotely doesn't involve dealing with how that is
achieved over SSH. There is now a unified pattern for both.


### Interfaces

A device _interface_ is a modular group of (related) operations that can be
performed on a device. When a device instance is created, a set of device
_interfaces_ are attached to it, thus defining the operations that can be
performed on the device.

Examples of interfaces:
- `RebootInterface`: reboot the device or check if a reboot is required
- `SystemStatusInterface`: check the (systemd) status of the device and
  wait until it reaches an allowed state
- `SnapdAPIClient`: interact with snapd REST API on the device
- `DebInterface`: manage Debian packages (install, add repositories, check
  for operations in progress)
- `SnapInterface`: manage snap packages (install/refresh, check for operations
  in progress)

#### Code example: query the snapd API

```python
from toolbox.devices.lab import LabDevice
from toolbox.interfaces.snapd import SnapdAPIClient

# the DEVICE_IP environment variable needs to be set
device = LabDevice(interfaces=[SnapdAPIClient()])

device.interfaces[SnapdAPIClient].get("system-info")
device.interfaces[SnapdAPIClient].get("connections", params={"select": "all"})
# returned as JSON, even though content-type is application/x.ubuntu.assertion
device.interfaces[SnapdAPIClient].get("model")
```

#### Code example: update/upgrade Debian packages

```python
from toolbox.devices.lab import LabDevice
from toolbox.interfaces.debs import DebInterface
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.status import SystemStatusInterface

# the DEVICE_IP environment variable needs to be set
device = LabDevice(interfaces=[DebInterface(), RebootInterface(), SystemStatusInterface()])

device.interfaces[DebInterface].update()
device.interfaces[DebInterface].upgrade()
device.interfaces[DebInterface].wait_for_complete()
device.interfaces[RebootInterface].reboot()
device.interfaces[SystemStatusInterface].wait_for_status(allowed=["degraded"])
```

#### Code example: install/refresh a snap

```python
from toolbox.devices.lab import LabDevice
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snaps import SnapInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.status import SystemStatusInterface

# the DEVICE_IP environment variable needs to be set
device = LabDevice(
    interfaces=[
        RebootInterface(),
        SnapdAPIClient(),
        SystemStatusInterface(),
        SnapInterface(),
    ]
)

device.interfaces[SnapInterface].install(
    "bluez", channel="latest/beta", options=["--devmode"], refresh_ok=True
)
```

Note that only the `SnapInterface` is actually used here, but this is a
complex interface that actually requires the three additional interfaces
that were attached to the device. If only the `SnapInterface` had been
attached then an error would have been raised, indicating which required
interfaces are missing.

## Deploying Checkbox

In Certification tests, Checkbox is installed on a remote device (either
through Debian packages or snaps) and also on the "agent" controlling
the device (from a matching version of the source).

Checkbox deployment is complex and, importantly, cannot be performed
through a single device interface since it spans both a device and
its agent.

The `toolbox` offers Checkbox installer classes for deploying Checkbox
through Debian and snap packages, with their common functionality implemented
in a base class.

#### Code example: install Checkbox from debs (only on the device)

```python
from toolbox.checkbox.installers.debs import CheckboxDebsInstaller
from toolbox.devices import LocalHost
from toolbox.devices.lab import LabDevice
from toolbox.entities.risk import Risk
from toolbox.interfaces.debs import DebInterface

# the DEVICE_IP environment variable needs to be set
device = LabDevice(interfaces=[DebInterface()])

installer = CheckboxDebsInstaller(device, agent=LocalHost(), risk=Risk.BETA)
installer.install_on_device()
```

#### Code example: install Checkbox from snaps (on the device)

```python
from snapstore.client import SnapstoreClient
from snapstore.craft import create_base_client
from toolbox.checkbox.installers.snaps import (
    CheckboxSnapsInstaller,
    TOKEN_ENVIRONMENT_VARIABLE,
)
from toolbox.devices import LocalHost
from toolbox.devices.lab import LabDevice
from toolbox.entities.snaps import SnapSpecifier
from toolbox.interfaces.reboot import RebootInterface
from toolbox.interfaces.snaps import SnapInterface
from toolbox.interfaces.snapd import SnapdAPIClient
from toolbox.interfaces.status import SystemStatusInterface

# the DEVICE_IP environment variable needs to be set
device = LabDevice(
    interfaces=[
        SystemStatusInterface(),
        RebootInterface(),
        SnapdAPIClient(),
        SnapInterface(),
    ]
)
# the UBUNTU_STORE_AUTH environment variable needs to be set
installer = CheckboxSnapsInstaller(
    device=device,
    agent=LocalHost(),
    frontends=[SnapSpecifier.from_string("checkbox-zapper=uc24/beta")],
    snapstore=SnapstoreClient(create_base_client(TOKEN_ENVIRONMENT_VARIABLE))
)
# this will also install Checkbox on the agent, from source
installer.install()
```

## CLI scripts

The modules in `toolbox.cli` offer entry points for command-line scripts that
can gradually replace the bash "scriptlets". The `pyproject.toml` file specifies
the link between the command-line scripts that will be installed along with
the `toolbox` package and the corresponding entry points:

```
[project.scripts]
wait-for-ssh = "toolbox.cli.wait_for_ssh:main"
wait-for-packages-complete = "toolbox.cli.wait_for_packages_complete:main"
wait-for-snap-changes = "toolbox.cli.wait_for_snap_changes:main"
install-checkbox-snaps = "toolbox.cli.install_checkbox_snaps:main"
install-checkbox-debs = "toolbox.cli.install_checkbox_debs:main"
```

## Testing locally with `multipass`

Apart from the package's unit tests, it is possible to perform manual
integration tests using `multipass` instances (i.e. lightweight VMs) as
remote devices. In the future, this could also serve as the basis of
automated integration tests.

Launch a named instance for any image you'd like to test with
(e.g. `noble`, `core22`, etc.):
```
IMAGE=core20
DEVICE=device-$IMAGE
multipass launch $IMAGE --name $DEVICE --disk 10GB
```

Set the instance up so that it can accept password-less SSH connections.
You only need to perform this step once for a new image.
```
echo "ubuntu:insecure" | multipass exec $DEVICE -- sudo chpasswd
ssh-keygen -t rsa -b 4096 -f ~/.ssh/$DEVICE-key -N "" -C "temporary-$DEVICE-key"
cat ~/.ssh/$DEVICE-key.pub | multipass exec $DEVICE -- bash -c "cat >> /home/ubuntu/.ssh/authorized_keys"
```

Now you can set the `DEVICE_IP` environment variable to point to the
instance's IP. Every time you create `LabDevice`, it will refer to this
specific instance.
```
export DEVICE_IP=$(multipass exec $DEVICE -- hostname -I | tr -d '[:space:]')
```

Run `poetry run python` from `cert-tools/toolbox` in order to launch a Python
interactive shell in a virtual environment where `toolbox` is installed.
Now you can manually perform tests with `toolbox`, treating the `multipass`
instance as the remote device:

```python
from toolbox.devices.lab import LabDevice
device = LabDevice()
device.run(["uname", "-n"])
```
This should output `device-core20`.
