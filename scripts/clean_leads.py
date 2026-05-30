"""Clean leads data — remove entries that look like bad data.
Filters out:
- company_name longer than 60 chars
- company_name containing '%'
- company_name looking like a personal name (too short, single word)
- company_name with '-' followed by long description

Usage: python scripts/clean_leads.py [input.json] [output.json]
"""
import json
import sys
import os

def is_name_likely_personal(name):
    """Check if name looks like a person's name instead of a company."""
    name = name.strip()
    # Single word that's not all caps (acronyms like SPA, KL, MY are OK)
    words = name.split()
    if len(words) <= 2 and len(name) < 15:
        # Likely a personal name if it matches name patterns
        common_first_names = ['ahmad', 'muhammad', 'mohd', 'mohamed', 'siti', 'nur', 'nurul',
                              'fatimah', 'ali', 'abu', 'lim', 'tan', 'wong', 'chan', 'chong',
                              'lee', 'kumar', 'raj', 'devi', 'mary', 'john', 'david', 'peter']
        if any(name.lower().startswith(n) for n in common_first_names):
            return True
    return False

def is_garbage(name):
    """Filter out garbage entries."""
    name = name.strip()
    if len(name) == 0:
        return True
    if len(name) > 60:
        return True
    if '%' in name:
        return True
    # Has '-' but not as part of a legitimate compound name
    if '-' in name:
        parts = name.split('-')
        # If any part after the first is very long, it's a description not a company
        for part in parts[1:]:
            if len(part.strip()) > 30:
                return True
    if is_name_likely_personal(name):
        return True
    return False

def clean_leads(leads):
    """Return cleaned leads and count of removed."""
    cleaned = []
    removed = []
    for lead in leads:
        name = lead.get('company_name', lead.get('name', ''))
        if is_garbage(name):
            removed.append(lead)
        else:
            cleaned.append(lead)
    return cleaned, removed

def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else 'recorded_leads.json'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'real_leads.json'
    
    # Try common locations
    for base in ['.', '/root/agentflow/data', '/root/agentflow/scripts']:
        path = os.path.join(base, input_path)
        if os.path.exists(path):
            input_path = path
            break
    
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        sys.exit(1)
    
    with open(input_path) as f:
        leads = json.load(f)
    
    cleaned, removed = clean_leads(leads)
    
    with open(output_path, 'w') as f:
        json.dump(cleaned, f, indent=2)
    
    print(f"Cleaned {len(cleaned)} leads (removed {len(removed)} garbage entries)")
    if removed:
        print("Removed:")
        for r in removed:
            print(f"  - {r.get('company_name', r.get('name', 'unknown'))}")

if __name__ == '__main__':
    main()
