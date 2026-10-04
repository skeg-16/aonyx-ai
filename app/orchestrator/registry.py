import jsonschema

class ToolPermission:
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    BLOCKED = "BLOCKED"

class ToolRegistry:
    def __init__(self):
        self.tools = {}
        
    def register(self, name, description, schema, permission, func, timeout=15):
        if permission == ToolPermission.BLOCKED:
            return
        self.tools[name] = {
            "name": name,
            "description": description,
            "schema": schema,
            "permission": permission,
            "func": func,
            "timeout": timeout
        }
        
    def get_tool(self, name):
        return self.tools.get(name)

    def validate_args(self, name, args):
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        try:
            jsonschema.validate(instance=args, schema=tool["schema"])
            # Strict mode: reject extra arguments
            allowed_keys = set(tool["schema"].get("properties", {}).keys())
            for key in args.keys():
                if key not in allowed_keys:
                    raise ValueError(f"Unknown argument '{key}' for tool '{name}'")
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Invalid arguments: {e.message}")
        return args

    def get_all_schemas(self):
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["schema"]
            }
            for t in self.tools.values()
        ]

registry = ToolRegistry()
