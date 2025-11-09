"""Test script for weighted prompt selection feature."""

import sys
sys.path.insert(0, 'src')

from src.config.types.config_value_weighted_string_list import ConfigValueWeightedStringList, WeightedString
import json

print("=" * 60)
print("Testing Weighted Prompt Selection Feature")
print("=" * 60)

# Test 1: Create weighted prompts
print("\n1. Creating weighted prompt list...")
prompts = [
    WeightedString("Prompt A", weight=2.0),
    WeightedString("Prompt B", weight=1.0),
    WeightedString("Prompt C", weight=1.0),
]

config = ConfigValueWeightedStringList(
    "test_prompt",
    "Test Prompt",
    "Test description",
    prompts,
    []
)

print(f"   Created {len(config.value)} weighted prompts")
for i, wp in enumerate(config.value):
    print(f"   - Prompt {i+1}: weight={wp.weight}, text='{wp.text[:50]}...'")

# Test 2: Test JSON serialization
print("\n2. Testing JSON serialization...")
json_str = config.to_json_string()
print(f"   JSON output:\n{json_str}")

# Test 3: Test JSON parsing
print("\n3. Testing JSON parsing...")
test_json = json.dumps([
    {"text": "First option", "weight": 3.0},
    {"text": "Second option", "weight": 1.5},
    {"text": "Third option", "weight": 0.5}
])
result = config.parse(test_json)
if result.is_success:
    print(f"   [OK] Parsed successfully!")
    print(f"   New list has {len(config.value)} prompts:")
    for wp in config.value:
        print(f"     - {wp}")
else:
    print(f"   [FAIL] Parse failed: {result.error_message}")

# Test 4: Test weighted random selection
print("\n4. Testing weighted random selection (1000 samples)...")
counts = {}
for _ in range(1000):
    selected = config.get_random_weighted_choice()
    counts[selected] = counts.get(selected, 0) + 1

print("   Selection frequency:")
total_weight = sum(wp.weight for wp in config.value)
for wp in config.value:
    actual_count = counts.get(wp.text, 0)
    expected_pct = (wp.weight / total_weight) * 100
    actual_pct = (actual_count / 1000) * 100
    print(f"     '{wp.text[:30]}...': {actual_count}/1000 ({actual_pct:.1f}%) [expected ~{expected_pct:.1f}%]")

# Test 5: Test invalid JSON handling
print("\n5. Testing invalid JSON handling...")
invalid_json = "not valid json"
result = config.parse(invalid_json)
if not result.is_success:
    print(f"   [OK] Correctly rejected invalid JSON")
    print(f"   Error message: {result.error_message[:80]}...")
else:
    print(f"   [FAIL] Should have rejected invalid JSON")

# Test 6: Test edge case - all weights are 0
print("\n6. Testing edge case - all weights are zero...")
zero_weight_prompts = [
    WeightedString("A", weight=0.0),
    WeightedString("B", weight=0.0),
]
config2 = ConfigValueWeightedStringList(
    "test2",
    "Test 2",
    "Test",
    zero_weight_prompts,
    []
)
try:
    selected = config2.get_random_weighted_choice()
    print(f"   [OK] Handled zero weights gracefully, selected: '{selected}'")
except Exception as e:
    print(f"   [FAIL] Failed with error: {e}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
