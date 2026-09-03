import requests
import unittest

from unittest.mock import patch, MagicMock

from checkbox_version_published import (
    SnapSpec,
    PackageSpec,
    get_snap_specs,
    get_snap_info_from_store,
    is_snap_available,
    check_snaps_availability,
    get_package_specs,
    check_packages_availability,
    check_availability,
    main,
)


class TestGetSnapSpecs(unittest.TestCase):
    def test_multiple_snaps_and_channels(self):
        # Test case for multiple snaps and channels
        yaml_content = {
            "required-snaps": [
                {
                    "name": "checkbox22",
                    "channels": ["latest/edge", "latest/stable"],
                    "architectures": ["amd64"],
                },
                {
                    "name": "checkbox23",
                    "channels": ["latest/beta"],
                    "architectures": ["arm64"],
                },
            ]
        }
        version = "3.0-dev10"
        expected_result = [
            SnapSpec("checkbox22", "3.0-dev10", "latest/edge", "amd64"),
            SnapSpec("checkbox22", "3.0-dev10", "latest/stable", "amd64"),
            SnapSpec("checkbox23", "3.0-dev10", "latest/beta", "arm64"),
        ]
        result = get_snap_specs(yaml_content, version)
        self.assertEqual(result, expected_result)

    def test_invalid_yaml_structure(self):
        # Test case for invalid YAML structure
        yaml_content = {
            "required-snaps": [
                {
                    "channel": "edge",
                    "source": "src1",
                    "package": "pkg1",
                    "versions": ["20.04"],
                    "architectures": ["amd64"],
                },
            ],
        }
        version = "3.0-dev10"
        with self.assertRaises(KeyError):
            get_snap_specs(yaml_content, version)

    def test_empty_yaml(self):
        # Test case and empty YAML
        yaml_content = {}
        version = "3.0-dev10"
        result = get_snap_specs(yaml_content, version)
        self.assertEqual(result, [])


class TestGetSnapInfoFromStore(unittest.TestCase):
    @patch("requests.get")
    def test_successful_request(self, mock_get):
        # Mocking the response from the Snapcraft API
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = (
            b'{"channel-map": [], "name": "test_snap", "snap-id": "some_id"}'
        )
        mock_get.return_value = mock_response

        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="stable",
            arch=["amd64"],
        )
        result = get_snap_info_from_store(snap_example)

        self.assertEqual(result["name"], "test_snap")
        self.assertEqual(result["snap-id"], "some_id")

    @patch("requests.get")
    def test_failed_request(self, mock_get):
        # Mocking a failed response from the Snapcraft API
        # that should yield a
        mock_response = requests.Response()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        snap_example = SnapSpec(
            name="non_existent_snap",
            version="1.0",
            channel="stable",
            arch=["amd64"],
        )

        with self.assertRaises(RuntimeError) as context:
            get_snap_info_from_store(snap_example)

        self.assertIn("Failed to get info", str(context.exception))


class TestIsSnapAvailable(unittest.TestCase):
    def test_snap_available_exact_match(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)

    def test_snap_not_available_in_channel(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/beta",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_snap_available_different_version(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="2.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_snap_available_different_architecture(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["arm64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_channel_not_split(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)

    def test_channel_split(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="custom/beta",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "custom/beta",
                        "architecture": "amd64",
                        "track": "custom",
                        "risk": "beta",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)


class TestCheckSnapsAvailability(unittest.TestCase):
    def setUp(self):
        self.snap_specs = [
            SnapSpec("snap1", "1.0", "stable", "amd64"),
            SnapSpec("snap2", "1.0", "stable", "amd64"),
        ]

    @patch("checkbox_version_published.get_snap_info_from_store")
    @patch("checkbox_version_published.is_snap_available")
    def test_snaps_all_available(self, mock_is_snap_available, mock_get_snap_info):
        # Mock responses to simulate all snaps being available
        mock_get_snap_info.return_value = {"some": "response"}
        mock_is_snap_available.return_value = True

        snaps_available = {snap_spec: False for snap_spec in self.snap_specs}
        check_snaps_availability(self.snap_specs, snaps_available)

        self.assertTrue(all(snaps_available.values()))

    @patch("checkbox_version_published.get_snap_info_from_store")
    @patch("checkbox_version_published.is_snap_available")
    def test_snaps_not_all_available(self, mock_is_snap_available, mock_get_snap_info):
        # Mock responses to simulate not all snaps being available
        mock_get_snap_info.return_value = {"some": "response"}
        mock_is_snap_available.side_effect = [
            True,
            False,
        ]  # First snap available, second not

        snaps_available = {snap_spec: False for snap_spec in self.snap_specs}
        check_snaps_availability(self.snap_specs, snaps_available)

        self.assertFalse(all(snaps_available.values()))

    @patch("checkbox_version_published.get_snap_info_from_store")
    @patch("checkbox_version_published.is_snap_available")
    def test_only_retry_snaps_not_available(
        self, mock_is_snap_available, mock_get_snap_info
    ):
        # Mock responses to simulate not all snaps being available and check
        # that only those snaps are retried
        mock_get_snap_info.return_value = {"some": "response"}
        mock_is_snap_available.side_effect = [True]

        # The first snap is already available, the second is not
        snaps_available = {
            self.snap_specs[0]: True,
            self.snap_specs[1]: False,
        }

        check_snaps_availability(self.snap_specs, snaps_available)

        # The first snap is not checked again
        mock_is_snap_available.assert_called_once()
        # All snaps are available
        self.assertTrue(all(snaps_available.values()))

    @patch("checkbox_version_published.get_snap_info_from_store")
    @patch("checkbox_version_published.is_snap_available")
    def test_request_exception_handling(
        self, mock_is_snap_available, mock_get_snap_info
    ):
        # Mock get_snap_info_from_store to raise a requests.RequestException
        #
        mock_get_snap_info.return_value = [
            requests.RequestException(),
            RuntimeError(),
        ]
        mock_is_snap_available.side_effect = [False, False]

        snaps_available = {snap_spec: False for snap_spec in self.snap_specs}

        check_snaps_availability(self.snap_specs, snaps_available)

        # Check if the function continues after the exception and processes the
        # two exceptions
        self.assertFalse(snaps_available[self.snap_specs[0]])
        self.assertFalse(snaps_available[self.snap_specs[1]])


class TestGetPackageSpecs(unittest.TestCase):
    def test_get_package_specs(self):
        sample_yaml_content = {
            "required-packages": [
                {
                    "channel": "edge",
                    "source": "src1",
                    "package": "pkg1",
                    "versions": ["20.04", "22.04"],
                    "architectures": ["amd64", "armhf"],
                },
                {
                    "channel": "edge",
                    "source": "src1",
                    "package": "pkg1",
                    "versions": ["18.04"],
                    "architectures": ["amd64"],
                },
                {
                    "channel": "edge",
                    "source": "src2",
                    "package": "pkg2",
                    "versions": ["20.04", "22.04"],
                    "architectures": ["all"],
                },
            ],
        }

        version = "3.0-dev10"
        expected_result = [
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "18.04", "amd64"),
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "amd64"),
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "armhf"),
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "22.04", "amd64"),
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "22.04", "armhf"),
            PackageSpec("edge", "src2", "pkg2", "3.0~dev10", "20.04", "all"),
            PackageSpec("edge", "src2", "pkg2", "3.0~dev10", "22.04", "all"),
        ]
        result = get_package_specs(sample_yaml_content, version)
        # The packages are sorted and all the packages are included
        self.assertEqual(result, expected_result)

    def test_invalid_yaml_structure(self):
        # Test case for invalid YAML structure
        yaml_content = {
            "required-packages": [
                {
                    "name": "checkbox22",
                    "channels": ["latest/edge"],
                    "architectures": ["amd64"],
                }
            ]
        }
        version = "3.0-dev10"
        with self.assertRaises(KeyError):
            get_package_specs(yaml_content, version)

    def test_empty_yaml(self):
        # Test case and empty YAML
        yaml_content = {}
        version = "3.0-dev10"
        result = get_package_specs(yaml_content, version)
        self.assertEqual(result, [])


class TestCheckPackagesAvailability(unittest.TestCase):
    def setUp(self):
        self.package_specs = [
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "amd64"),
            PackageSpec("edge", "src2", "pkg2", "3.0~dev10", "22.04", "arm64"),
        ]

    def get_available_package_html(self, package_spec: PackageSpec):
        name = (
            f"{package_spec.package}_{package_spec.version}~ubuntu"
            f"{package_spec.ubuntu_version}.1_{package_spec.arch}.deb"
        )
        return f"<td><a href={name}>{name}</a></td>"

    @patch("requests.get")
    def test_all_packages_available(self, mock_url_get):
        # Mock url_header_check to simulate all packages being available
        mock_url_get.side_effect = [
            MagicMock(text=self.get_available_package_html(x))
            for x in self.package_specs
        ]
        packages_available = {
            package_spec: False for package_spec in self.package_specs
        }
        check_packages_availability(self.package_specs, packages_available)

        self.assertTrue(all(packages_available.values()))

    @patch("requests.get")
    def test_some_packages_not_available(self, mock_url_get):
        mock_url_get.side_effect = [
            MagicMock(text=self.get_available_package_html(self.package_specs[0])),
            MagicMock(text=""),
        ]
        packages_available = {
            package_spec: False for package_spec in self.package_specs
        }
        check_packages_availability(self.package_specs, packages_available)

        self.assertTrue(packages_available[self.package_specs[0]])
        self.assertFalse(packages_available[self.package_specs[1]])

    @patch("requests.get")
    def test_only_retry_packages_not_available(self, mock_url_get):
        # Mock url_header_check to simulate some packages not being available
        # and check that only those packages are retried
        mock_url_get.return_value.text = self.get_available_package_html(
            self.package_specs[1]
        )

        # The first package is already available, the second is not
        packages_available = {
            self.package_specs[0]: True,
            self.package_specs[1]: False,
        }

        check_packages_availability(self.package_specs, packages_available)

        # The first package is not checked again
        mock_url_get.assert_called_once()
        # All packages are available
        self.assertTrue(all(packages_available.values()))


class TestCheckAvailability(unittest.TestCase):
    def setUp(self):
        self.snap_specs = [SnapSpec("snap1", "1.0", "stable", "amd64")]
        self.package_specs = [
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "amd64")
        ]

    @patch("checkbox_version_published.check_snaps_availability")
    @patch("checkbox_version_published.check_packages_availability")
    def test_all_available_before_timeout(self, mock_check_packages, mock_check_snaps):
        mock_check_snaps.side_effect = lambda specs, avail: avail.update(
            (spec, True) for spec in specs
        )
        mock_check_packages.side_effect = lambda specs, avail: avail.update(
            (spec, True) for spec in specs
        )

        check_availability(self.snap_specs, self.package_specs, 60)

    @patch("checkbox_version_published.check_snaps_availability")
    @patch("checkbox_version_published.check_packages_availability")
    @patch("time.time")
    @patch("time.sleep")
    def test_timeout_reached(
        self, mock_sleep, mock_time, mock_check_packages, mock_check_snaps
    ):
        start_time = 0  # Arbitrary start time
        mock_time.side_effect = [
            start_time,
            start_time,
            start_time + 61,
        ]  # Simulate time passage to trigger timeout

        mock_check_snaps.side_effect = lambda specs, avail: avail.update(
            (spec, False) for spec in specs
        )
        mock_check_packages.side_effect = lambda specs, avail: avail.update(
            (spec, False) for spec in specs
        )

        with self.assertRaises(TimeoutError):
            check_availability(self.snap_specs, self.package_specs, 60)


class TestMain(unittest.TestCase):
    @patch("builtins.open")
    @patch("checkbox_version_published.yaml.load")
    @patch("checkbox_version_published.check_availability")
    def test_argument_parsing(self, mock_check, mock_yaml_load, mock_open):
        argv = [
            "script_name",
            "3.0-dev10",
            "checkbox-canary.yaml",
            "--timeout",
            "100",
        ]

        yaml_content = {
            "required-snaps": [
                {
                    "name": "snap1",
                    "channels": ["edge"],
                    "architectures": ["amd64", "armhf"],
                }
            ],
            "required-packages": [
                {
                    "channel": "edge",
                    "source": "src1",
                    "package": "pkg1",
                    "versions": ["20.04"],
                    "architectures": ["amd64", "armhf"],
                },
            ],
        }

        # Mock the YAML files
        mock_yaml_load.side_effect = [yaml_content]

        # Run the main function
        main(argv)
        snap_specs, package_specs, timeout = mock_check.call_args[0]
        # check_availability is called with the expected arguments
        # snap specs
        expected_snap_specs = [
            SnapSpec("snap1", "3.0-dev10", "edge", "amd64"),
            SnapSpec("snap1", "3.0-dev10", "edge", "armhf"),
        ]
        self.assertEqual(snap_specs, expected_snap_specs)
        # package specs
        expected_package_specs = [
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "amd64"),
            PackageSpec("edge", "src1", "pkg1", "3.0~dev10", "20.04", "armhf"),
        ]
        self.assertEqual(package_specs, expected_package_specs)
        # The timeout is 100
        self.assertEqual(timeout, 100)

    def test_main_fails_with_missing_arguments(self):
        # Simulate missing YAML file argument
        argv = ["script_name", "3.0~dev10", "--timeout", "100"]

        with self.assertRaises(SystemExit):
            main(argv)

    @patch("builtins.open")
    @patch("checkbox_version_published.yaml.load")
    def test_invalid_yaml(self, mock_yaml_load, mock_open):
        argv = [
            "script_name",
            "3.0-dev10",
            "checkbox-canary.yaml",
            "--timeout",
            "100",
        ]

        # Empty YAML content
        yaml_content = []

        # Mock the YAML files
        mock_yaml_load.side_effect = [yaml_content]

        # Run the main function
        with self.assertRaises(ValueError) as e:
            main(argv)

        self.assertEqual("The YAML content is invalid.", str(e.exception))
