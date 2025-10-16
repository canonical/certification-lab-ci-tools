from toolbox.devices import Device


class DeviceInterface:
    def __init__(self, device: Device):
        self.device = device
