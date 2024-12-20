import os
import plantuml
from pathlib import Path

def generate_diagrams():
    # Initialize PlantUML
    puml = plantuml.PlantUML(url='http://www.plantuml.com/plantuml/png/')
    
    # Ensure static images directory exists
    Path('app/static/images').mkdir(parents=True, exist_ok=True)
    
    # Define source and destination paths
    diagrams = {
        'app/diagrams/diagram.puml': 'app/static/images/component-diagram.png',
        'app/diagrams/database.puml': 'app/static/images/database-schema.png',
        'app/diagrams/summary.puml': 'app/static/images/summary-diagram.png'
    }
    
    for source, dest in diagrams.items():
        try:
            with open(source, 'r') as f:
                puml_content = f.read()
            
            # Remove line numbers if present
            cleaned_content = '\n'.join(
                line.split('|')[1] if '|' in line else line 
                for line in puml_content.splitlines()
            )
            
            # Generate PNG
            png_data = puml.processes(cleaned_content)
            
            # Save to file
            with open(dest, 'wb') as f:
                f.write(png_data)
            
            print(f"✓ Generated {dest}")
            
        except Exception as e:
            print(f"❌ Error processing {source}: {str(e)}")

if __name__ == "__main__":
    generate_diagrams() 