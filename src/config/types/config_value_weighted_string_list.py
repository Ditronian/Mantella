import json
import random
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConfigValueTag


class WeightedString:
    """Represents a single string with an associated weight for random selection."""

    def __init__(self, text: str, weight: float = 1.0):
        self.text = text
        self.weight = max(0.0, weight)  # Ensure non-negative weight

    def to_dict(self) -> dict:
        return {"text": self.text, "weight": self.weight}

    @staticmethod
    def from_dict(data: dict) -> 'WeightedString':
        return WeightedString(data.get("text", ""), data.get("weight", 1.0))

    def __repr__(self) -> str:
        return f"WeightedString(text='{self.text[:50]}...', weight={self.weight})"


class ConfigValueWeightedStringList(ConfigValue[list[WeightedString]]):
    """Config value that stores multiple strings with weights for random selection."""

    def __init__(self, identifier: str, name: str, description: str,
                 default_value: list[WeightedString],
                 constraints: list[ConfigValueConstraint[list[WeightedString]]] = [],
                 is_hidden: bool = False,
                 tags: list[ConfigValueTag] = []):
        super().__init__(identifier, name, description, default_value, constraints, is_hidden, tags)

    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        """Parse JSON string from config.ini into list of WeightedString objects."""
        try:
            # Parse JSON from config
            json_data = json.loads(config_value)

            # Convert to WeightedString objects
            if isinstance(json_data, list):
                weighted_strings = [WeightedString.from_dict(item) for item in json_data]
            else:
                return ConfigValueConstraintResult(
                    f"Error when reading config value '{self.identifier}'. Expected JSON array."
                )

            # Apply constraints
            result = self.does_value_cause_error(weighted_strings)
            if result.is_success:
                self.value = weighted_strings
                return ConfigValueConstraintResult()
            else:
                return result

        except json.JSONDecodeError as e:
            return ConfigValueConstraintResult(
                f"Error when reading config value '{self.identifier}'. Invalid JSON: {str(e)}"
            )
        except Exception as e:
            return ConfigValueConstraintResult(
                f"Error when reading config value '{self.identifier}'. {str(e)}"
            )

    def get_random_weighted_choice(self) -> str:
        """Select and return a random string based on weights."""
        if not self.value:
            return ""

        # Extract texts and weights
        texts = [ws.text for ws in self.value]
        weights = [ws.weight for ws in self.value]

        # Handle case where all weights are 0
        if sum(weights) == 0:
            return random.choice(texts)

        # Use random.choices with weights
        return random.choices(texts, weights=weights, k=1)[0]

    def to_json_string(self) -> str:
        """Convert current value to JSON string for config.ini storage."""
        json_data = [ws.to_dict() for ws in self.value]
        return json.dumps(json_data, indent=2)

    def default_value_to_json(self) -> str:
        """Convert default value to JSON string for config.ini storage."""
        json_data = [ws.to_dict() for ws in self.default_value]
        return json.dumps(json_data, indent=2)

    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueWeightedStringList(self)

    def __str__(self) -> str:
        """String representation for config file writing."""
        return self.to_json_string()
