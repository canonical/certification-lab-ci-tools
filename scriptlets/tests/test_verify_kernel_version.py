from unittest.mock import patch

import pytest

from verify_kernel_version import (
    EXIT_FAILURE,
    EXIT_OK,
    booted_expected_kernel,
    main,
    parse_booted_version,
    read_version_signature,
    verify,
)


@pytest.mark.parametrize(
    "signature, expected",
    [
        ("Ubuntu 6.8.0-130.130-generic 6.8.12", "6.8.0-130.130-generic"),
        ("", ""),
        ("Ubuntu", ""),
    ],
)
def test_parse_booted_version(signature, expected):
    assert parse_booted_version(signature) == expected


@pytest.mark.parametrize(
    "booted_version_flavour, expected_version, expected",
    [
        ("6.8.0-130.130-generic", "6.8.0-130.130", True),
        ("6.8.0-131.131-generic", "6.8.0-130.130", False),
        # "6.8.0-130.13" must not match "6.8.0-130.130-generic": the trailing
        # dash in the expected prefix guards against partial-number matches.
        ("6.8.0-130.130-generic", "6.8.0-130.13", False),
    ],
)
def test_booted_expected_kernel(
    booted_version_flavour, expected_version, expected
):
    assert (
        booted_expected_kernel(booted_version_flavour, expected_version)
        is expected
    )


@pytest.mark.parametrize(
    "signature, expected_version, expected_exit_code, expected_message",
    [
        (
            "Ubuntu 6.8.0-130.130-generic 6.8.12",
            "6.8.0-130.130",
            EXIT_OK,
            "Kernel verification OK: device booted expected kernel "
            "6.8.0-130.130 (6.8.0-130.130-generic)",
        ),
        (
            "Ubuntu 6.8.0-131.131-generic 6.8.12",
            "6.8.0-130.130",
            EXIT_FAILURE,
            "does not match the expected version",
        ),
        (
            "",
            "6.8.0-130.130",
            EXIT_FAILURE,
            "could not determine the booted kernel version",
        ),
    ],
)
def test_verify(
    capsys, signature, expected_version, expected_exit_code, expected_message
):
    exit_code = verify(signature, expected_version)
    assert exit_code == expected_exit_code
    assert expected_message in capsys.readouterr().out


def test_read_version_signature(tmp_path):
    signature = "Ubuntu 6.8.0-130.130-generic 6.8.12"
    signature_file = tmp_path / "version_signature"
    signature_file.write_text(f"{signature}\n", encoding="utf-8")
    assert read_version_signature(str(signature_file)) == signature


@pytest.mark.parametrize(
    "signature, expected_version, expected_exit_code",
    [
        ("Ubuntu 6.8.0-130.130-generic 6.8.12", "6.8.0-130.130", EXIT_OK),
        ("Ubuntu 6.8.0-131.131-generic 6.8.12", "6.8.0-130.130", EXIT_FAILURE),
    ],
)
def test_main(signature, expected_version, expected_exit_code):
    with patch(
        "verify_kernel_version.read_version_signature",
        return_value=signature,
    ):
        exit_code = main([expected_version])
    assert exit_code == expected_exit_code
