import ast
import os
import importlib.util
from pathlib import Path

def is_module_available(module_path, base_dir):
    """Check if a module exists in the project structure"""
    # Handle absolute imports starting with 'app.'
    if module_path.startswith('app.'):
        module_path = module_path[4:]  # Remove 'app.' prefix
    
    # Convert module path to file path
    file_path = os.path.join(base_dir, *module_path.split('.'))
    
    # Check for both .py file and directory with __init__.py
    return (
        os.path.exists(f"{file_path}.py") or
        (os.path.isdir(file_path) and 
         os.path.exists(os.path.join(file_path, "__init__.py")))
    )

def verify_imports(directory):
    issues = []
    base_dir = os.path.join(os.path.dirname(directory), 'app')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    try:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom):
                                if node.module:
                                    # Check if import should be app-prefixed
                                    if not node.module.startswith('app.'):
                                        if is_module_available(f"app.{node.module}", base_dir):
                                            issues.append(
                                                f"{filepath}: Should use 'app.{node.module}' "
                                                f"instead of '{node.module}'"
                                            )
                                    # Verify the import path exists
                                    elif not is_module_available(node.module, base_dir):
                                        issues.append(
                                            f"{filepath}: Import path '{node.module}' "
                                            f"does not exist"
                                        )
                            elif isinstance(node, ast.Import):
                                for alias in node.names:
                                    if not alias.name.startswith(('app.', 'flask', 'plaid', 'psycopg2')):
                                        if is_module_available(f"app.{alias.name}", base_dir):
                                            issues.append(
                                                f"{filepath}: Should use 'app.{alias.name}' "
                                                f"instead of '{alias.name}'"
                                            )
                    except Exception as e:
                        issues.append(f"Error parsing {filepath}: {str(e)}")
    
    return issues

if __name__ == "__main__":
    issues = verify_imports("app")
    if issues:
        print("Found import issues:")
        for issue in issues:
            print(f"- {issue}")
        exit(1)
    else:
        print("No import issues found!") 