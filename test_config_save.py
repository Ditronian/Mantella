"""Test that weighted prompts are correctly saved to config.ini format."""

import sys
sys.path.insert(0, 'src')

from src.config.types.config_value_weighted_string_list import ConfigValueWeightedStringList, WeightedString
from src.config.config_file_writer import ConfigFileWriter
from src.config.types.config_value_group import ConfigValueGroup

print("=" * 60)
print("Testing Config.ini Save Functionality")
print("=" * 60)

# Create a weighted prompt config value
prompts = [
    WeightedString("First prompt option", weight=2.0),
    WeightedString("Second prompt option", weight=1.0),
    WeightedString("Third prompt option", weight=1.5),
]

config_value = ConfigValueWeightedStringList(
    "npc_auto_continue_prompt",
    "NPC Auto-Continuation Prompts",
    "Test weighted prompts that will be randomly selected",
    prompts,
    []
)

# Create a test config values object
from src.config.config_values import ConfigValues
test_values = ConfigValues()
test_group = ConfigValueGroup("TestGroup", "Test Group", "Test description")
test_group.add_config_value(config_value)
test_values.add_base_group(test_group)

# Write to a test file
test_file_path = "test_config_output.ini"
writer = ConfigFileWriter()

print(f"\n1. Writing weighted prompts to {test_file_path}...")
writer.write(test_file_path, test_values)

print("   Done!")

# Read back the file and display it
print(f"\n2. Reading back the written config:")
print("-" * 60)
with open(test_file_path, 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
print("-" * 60)

# Test parsing it back
print("\n3. Testing parsing the saved config...")
import configparser
config = configparser.ConfigParser()
config.read(test_file_path, encoding='utf-8')

saved_value = config.get('TestGroup', 'npc_auto_continue_prompt')
print(f"   Raw value from config file:\n{saved_value}")

# Try to parse it
print("\n4. Parsing the JSON value...")
parse_result = config_value.parse(saved_value)
if parse_result.is_success:
    print(f"   [OK] Parsed successfully!")
    print(f"   Loaded {len(config_value.value)} prompts:")
    for i, wp in enumerate(config_value.value):
        print(f"     {i+1}. weight={wp.weight}, text='{wp.text}'")
else:
    print(f"   [FAIL] Parse failed: {parse_result.error_message}")

# Clean up
import os
os.remove(test_file_path)
print(f"\n5. Cleaned up test file")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
