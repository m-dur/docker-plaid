import os
import subprocess
from pathlib import Path

def ensure_output_directory():
    """Create output directory for diagrams if it doesn't exist"""
    output_dir = Path("app/static/images/diagrams")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def generate_diagram(puml_file: Path, output_dir: Path):
    """Generate PNG diagram from PlantUML file"""
    # Replace spaces with underscores in the output filename
    output_filename = puml_file.stem.replace(' ', '_') + '.png'
    output_file = output_dir / output_filename
    
    try:
        # Run PlantUML command
        result = subprocess.run([
            'plantuml',
            '-tpng',
            '-output',
            str(output_dir),
            str(puml_file)
        ], capture_output=True, text=True)
        
        # Rename the output file if it exists
        default_output = output_dir / f"{puml_file.stem}.png"
        if default_output.exists():
            default_output.rename(output_file)
        
        if result.returncode == 0:
            print(f"✅ Successfully generated {output_file}")
        else:
            print(f"❌ Error generating {puml_file.name}:")
            print(result.stderr)
            
    except FileNotFoundError:
        print("❌ Error: PlantUML not found. Please install PlantUML first.")
        print("Installation instructions:")
        print("1. Install Java (required for PlantUML)")
        print("2. Install PlantUML:")
        print("   - On macOS: brew install plantuml")
        print("   - On Ubuntu: sudo apt-get install plantuml")
        print("   - On Windows: Download from https://plantuml.com/download")
        exit(1)

def main():
    # Setup directories
    diagrams_dir = Path("app/diagrams")
    output_dir = ensure_output_directory()
    
    # Check if diagrams directory exists
    if not diagrams_dir.exists():
        print(f"❌ Error: Diagrams directory not found at {diagrams_dir}")
        exit(1)
    
    # Process all .puml files
    puml_files = list(diagrams_dir.glob("*.puml"))
    
    if not puml_files:
        print("❌ No .puml files found in diagrams directory")
        exit(1)
    
    print(f"🔍 Found {len(puml_files)} PlantUML files")
    
    # Generate diagrams
    for puml_file in puml_files:
        print(f"\n🔄 Processing {puml_file.name}...")
        generate_diagram(puml_file, output_dir)

if __name__ == "__main__":
    main()