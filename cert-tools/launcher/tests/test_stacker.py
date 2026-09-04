import pytest
from launcher.configuration import CheckBoxConfiguration


def create_config_file(tmp_path, filename, content):
    """
    Helper function to create config files for testing.
    """
    path = tmp_path / filename
    stacker = CheckBoxConfiguration()
    stacker.read_string(content)
    stacker.write_to_file(path)
    return path


@pytest.fixture
def config_files(tmp_path):
    """
    Pytest fixture that creates multiple configuration files for testing.
    """
    configs = {
        "config1": """
        [section_1]
        key_11 = config1_value_11
        key_12 = config1_value_12
        """,
        "config2": """
        [section_2]
        key_21 = config2_value_21
        key_22 = config2_value_22
        """,
        "config12": """
        [section_1]
        key_11 = config12_value_11
        [section_2]
        key_22 = config12_value_22
        [launcher]
        key_l1 = launcher_value
        """,
        "config_launcher": """
        [launcher]
        session_desc = placeholder
        """,
    }
    paths = {}
    for name, content in configs.items():
        path = create_config_file(tmp_path, name, content)
        paths[name] = path
        with open(path) as file:
            contents = file.read()
            print(path)
            print(contents)
    return paths


def test_stack_invalid_filename(config_files):
    """
    Non-existent files should raise a `FileNotFoundError`
    """
    with pytest.raises(FileNotFoundError):
        CheckBoxConfiguration().stack(
            paths=["nonexistent", config_files["config1"]], output="stacked.conf"
        )


def test_stack_no_overlap(config_files):
    """
    Stack non-overlapping configurations
    """
    CheckBoxConfiguration().stack(
        paths=[config_files["config1"], config_files["config2"]], output="stacked.conf"
    )

    stacked = CheckBoxConfiguration()
    stacked.read("stacked.conf")

    assert stacked["section_1"]["key_11"] == "config1_value_11"
    assert stacked["section_2"]["key_22"] == "config2_value_22"


def test_stack_overlap(config_files):
    """
    Stack overlapping configurations and check overrides
    """
    CheckBoxConfiguration().stack(
        paths=[
            config_files["config1"],
            config_files["config12"],
            config_files["config2"],
        ],
        output="stacked.conf",
    )

    stacked = CheckBoxConfiguration()
    stacked.read("stacked.conf")

    # config_12 overrides section_1 -> key_11 from config_1
    assert stacked["section_1"]["key_11"] == "config12_value_11"
    # config_2 overrides section_1 -> key_11 from config_12
    assert stacked["section_2"]["key_22"] == "config2_value_22"


def test_description_without_launcher(config_files):
    """
    Add a description that creates a `launcher` section
    """
    CheckBoxConfiguration().stack(
        paths=[
            config_files["config1"],
        ],
        output="stacked.conf",
        description="description",
    )

    stacked = CheckBoxConfiguration()
    stacked.read("stacked.conf")

    assert stacked["launcher"]["session_desc"] == "description"


def test_description_with_launcher(config_files):
    """
    Add a description into an existing `launcher` section
    """
    CheckBoxConfiguration().stack(
        paths=[
            config_files["config12"],
        ],
        output="stacked.conf",
        description="description",
    )

    stacked = CheckBoxConfiguration()
    stacked.read("stacked.conf")

    assert stacked["launcher"]["session_desc"] == "description"


def test_description_with_description(config_files):
    """
    Add a description over an existing one
    """
    CheckBoxConfiguration().stack(
        paths=[
            config_files["config_launcher"],
        ],
        output="stacked.conf",
        description="description",
    )

    stacked = CheckBoxConfiguration()
    stacked.read("stacked.conf")

    assert stacked["launcher"]["session_desc"] == "description"
