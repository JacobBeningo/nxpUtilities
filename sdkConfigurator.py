#!/usr/bin/env python3
"""
NXP West Manifest GUI Configurator using Tkinter
Provides a visual interface for selecting manifest components.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import yaml
import json
import requests
from pathlib import Path
from typing import Dict, Any, List, Union
import threading
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ManifestConfig:
    """Configuration for manifest generation."""
    imports: Dict[str, Union[bool, List[str]]] = field(default_factory=dict)
    group_filters: List[str] = field(default_factory=list)
    use_nxp_remotes: bool = True
    use_nxp_defaults: bool = True
    use_nxp_west_commands: bool = True
    created_at: str = None
    nxp_manifest_revision: str = "main"
    nxp_manifest_url: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class ManifestExplorer:
    """Explore NXP manifest structure."""
    
    def __init__(self, manifest_url: str = None):
        self.manifest_url = manifest_url or "https://raw.githubusercontent.com/nxp-mcuxpresso/mcuxsdk-manifests/main/west.yml"
        self.base_url = "/".join(self.manifest_url.split("/")[:-1])
        self.manifest = None
        self.import_structure = {}
        
    def fetch_manifest(self) -> Dict[str, Any]:
        """Fetch the main NXP manifest."""
        response = requests.get(self.manifest_url)
        response.raise_for_status()
        self.manifest = yaml.safe_load(response.text)
        return self.manifest
    
    def analyze_imports(self) -> Dict[str, Any]:
        """Analyze the import structure dynamically."""
        if not self.manifest:
            self.fetch_manifest()
        
        imports = self.manifest.get('manifest', {}).get('self', {}).get('import', [])
        structure = {}
        
        for import_path in imports:
            if isinstance(import_path, str):
                structure[import_path] = self._analyze_import_path(import_path)
        
        self.import_structure = structure
        return structure
    
    def _analyze_import_path(self, path: str) -> Dict[str, Any]:
        """Analyze a single import path."""
        info = {
            'path': path,
            'type': 'unknown',
            'contents': []
        }
        
        if path.endswith('.yml'):
            info['type'] = 'file'
            info['filename'] = Path(path).name
        elif path.endswith('/'):
            info['type'] = 'directory'
            # Always fetch directory contents
            info['contents'] = self._fetch_directory_contents(path)
        else:
            # Ambiguous - could be file or directory
            # First check if it's a directory by trying with trailing slash
            dir_contents = self._fetch_directory_contents(path + '/')
            if dir_contents:
                info['type'] = 'directory'
                info['contents'] = dir_contents
                info['path'] = path + '/'  # Normalize to include trailing slash
            else:
                # Assume it's a file
                info['type'] = 'file'
                info['filename'] = Path(path).name
        
        return info
    
    def _fetch_directory_contents(self, dir_path: str) -> List[Dict[str, str]]:
        """Fetch contents of a directory from GitHub."""
        api_url = self.manifest_url.replace(
            'raw.githubusercontent.com',
            'api.github.com/repos'
        ).replace('/main/', '/contents/').replace('/west.yml', f'/{dir_path}')
        
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                files = response.json()
                contents = []
                for f in files:
                    if f['name'].endswith('.yml'):
                        contents.append({
                            'name': f['name'].replace('.yml', ''),
                            'filename': f['name'],
                            'path': dir_path + f['name']
                        })
                return contents
        except:
            pass
        return []
    
    def get_all_configuration(self) -> Dict[str, Any]:
        """Get all configuration from the manifest."""
        return {
            'remotes': self.manifest.get('manifest', {}).get('remotes', []),
            'defaults': self.manifest.get('manifest', {}).get('defaults', {}),
            'group-filter': self.manifest.get('manifest', {}).get('group-filter', []),
            'self': self.manifest.get('manifest', {}).get('self', {}),
        }


class ManifestConfiguratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NXP West Manifest Configurator")
        self.root.geometry("1000x800")
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Data
        self.explorer = ManifestExplorer()
        self.config = ManifestConfig()
        self.import_vars = {}  # Store checkbox variables
        self.directory_selections = {}  # Store directory selections
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        """Create all UI widgets with a sidebar/main layout."""
        # Main container
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame = ttk.Frame(self.root, padding=0)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Sidebar (Imports) ---
        sidebar = tk.Frame(main_frame, width=420, bg='#f5f5f5', bd=1, relief=tk.GROOVE)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Title in sidebar
        title_label = ttk.Label(sidebar, text="NXP West Manifest Configurator", 
                               font=('Helvetica', 15, 'bold'), background='#f5f5f5')
        title_label.pack(pady=(18, 10), padx=10, anchor=tk.W)

        # Filter bar
        filter_frame = ttk.Frame(sidebar)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', self.apply_filter)
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Clear", command=lambda: self.filter_var.set("")).pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # Scrollable imports/categories area
        imports_container = tk.Frame(sidebar, bg='#f5f5f5')
        imports_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 10))
        imports_canvas = tk.Canvas(imports_container, borderwidth=0, highlightthickness=0, bg='#f5f5f5')
        imports_scrollbar = ttk.Scrollbar(imports_container, orient="vertical", command=imports_canvas.yview)
        self.imports_content = tk.Frame(imports_canvas, bg='#f5f5f5')
        self.imports_content.bind(
            "<Configure>", lambda e: imports_canvas.configure(scrollregion=imports_canvas.bbox("all")))
        imports_window = imports_canvas.create_window((0, 0), window=self.imports_content, anchor="nw")
        imports_canvas.configure(yscrollcommand=imports_scrollbar.set)
        imports_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        imports_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Main area (Notebook: Preview/Settings) ---
        main_area = ttk.Frame(main_frame)
        main_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Control buttons (top of main area)
        control_frame = ttk.Frame(main_area)
        control_frame.pack(fill=tk.X, padx=20, pady=(18, 10))
        ttk.Button(control_frame, text="Load NXP Manifest", 
                  command=self.load_manifest).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load Config", 
                  command=self.load_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Save Config", 
                  command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Generate Manifest", 
                  command=self.generate_manifest).pack(side=tk.LEFT, padx=5)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_area)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.create_settings_tab()
        self.create_preview_tab()
        # Make Preview tab the default
        self.notebook.select(1)

        # Status bar
        self.status_var = tk.StringVar(value="Ready. Click 'Load NXP Manifest' to begin.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_imports_tab(self):
        """Create the imports configuration tab (for the notebook, not the whole layout)."""
        imports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(imports_frame, text="Imports")
        # The actual imports UI is now in the sidebar, so this tab can be left empty or used for help/info.
        ttk.Label(imports_frame, text="Use the sidebar to configure imports.", font=("Helvetica", 12, "italic"), foreground="#888").pack(padx=20, pady=20)
        
    def apply_filter(self, *args):
        """Apply filter to show/hide import options."""
        filter_text = self.filter_var.get().lower()
        
        if not filter_text:
            # Show all
            for widget in self.imports_content.winfo_children():
                widget.grid()
        else:
            # Hide non-matching
            for widget in self.imports_content.winfo_children():
                if isinstance(widget, ttk.LabelFrame):
                    if filter_text in widget.cget('text').lower():
                        widget.grid()
                    else:
                        widget.grid_remove()
                elif isinstance(widget, ttk.Label):
                    # Keep category labels visible if any child matches
                    widget.grid()
        
    def create_settings_tab(self):
        """Create the settings tab."""
        settings_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(settings_frame, text="Settings")
        
        # Base settings
        ttk.Label(settings_frame, text="Base Configuration", 
                 font=('Helvetica', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        self.use_remotes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Use NXP remote repositories", 
                       variable=self.use_remotes_var).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.use_defaults_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Use NXP default settings", 
                       variable=self.use_defaults_var).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.use_commands_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Use NXP west commands", 
                       variable=self.use_commands_var).grid(row=3, column=0, sticky=tk.W, pady=5)
        
        # Group filters
        ttk.Label(settings_frame, text="Group Filters", 
                 font=('Helvetica', 12, 'bold')).grid(row=4, column=0, columnspan=2, pady=(20, 10))
        
        ttk.Label(settings_frame, text="One per line (e.g., -optional, +required):").grid(row=5, column=0, sticky=tk.W)
        
        self.group_filters_text = scrolledtext.ScrolledText(settings_frame, height=10, width=40)
        self.group_filters_text.grid(row=6, column=0, columnspan=2, pady=10)
        
    def create_preview_tab(self):
        """Create the preview tab."""
        preview_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(preview_frame, text="Preview")
        
        # Preview text with larger font
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=30, width=80, font=("Consolas", 14))
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(preview_controls, text="Update Preview", 
                  command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(preview_controls, text="Copy to Clipboard", 
                  command=self.copy_preview).pack(side=tk.LEFT, padx=5)
        
    def load_manifest(self):
        """Load and analyze NXP manifest."""
        self.status_var.set("Loading NXP manifest...")
        
        # Show progress
        progress = ttk.Progressbar(self.root, mode='indeterminate')
        progress.place(relx=0.5, rely=0.5, anchor='center')
        progress.start()
        
        # Run in thread to avoid blocking UI
        def load():
            try:
                self.status_var.set("Fetching manifest...")
                self.explorer.fetch_manifest()
                
                self.status_var.set("Analyzing import structure...")
                import_structure = self.explorer.analyze_imports()
                
                # Count directories to fetch
                dirs_to_fetch = sum(1 for info in import_structure.values() 
                                   if info.get('type') == 'directory')
                
                if dirs_to_fetch > 0:
                    self.status_var.set(f"Fetching contents of {dirs_to_fetch} directories...")
                
                # Update UI in main thread
                self.root.after(0, self.populate_imports, import_structure)
                self.root.after(0, self.populate_settings)
                self.root.after(0, lambda: self.status_var.set("Manifest loaded successfully!"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load manifest: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set("Failed to load manifest"))
            finally:
                self.root.after(0, progress.destroy)
        
        thread = threading.Thread(target=load)
        thread.start()
        
    def populate_imports(self, import_structure):
        """Populate the imports tab with checkboxes."""
        # Clear existing content
        for widget in self.imports_content.winfo_children():
            widget.destroy()
        self.import_vars.clear()
        self.directory_selections.clear()
        
        # Create categories based on path structure
        categories = {
            'Base Files': [],
            'Devices': [],
            'Middleware': [],
            'RTOS': [],
            'Other': []
        }
        
        # Categorize imports
        for path, info in import_structure.items():
            # Normalize path for comparison
            norm_path = info.get('path', path)
            
            if 'base.yml' in norm_path or 'internal.yml' in norm_path:
                categories['Base Files'].append((norm_path, info))
            elif 'devices' in norm_path:
                categories['Devices'].append((norm_path, info))
            elif 'middleware' in norm_path:
                categories['Middleware'].append((norm_path, info))
            elif 'rtos' in norm_path:
                categories['RTOS'].append((norm_path, info))
            else:
                categories['Other'].append((norm_path, info))
        
        # Create UI for each category
        for category, items in categories.items():
            if items:  # Only create sections for non-empty categories
                self.create_category_section(self.imports_content, category, items)
        
    def create_category_section(self, parent, category_name, items):
        """Create a section for a category of imports."""
        # Category header
        cat_frame = ttk.LabelFrame(parent, text=category_name, padding="10")
        cat_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Process items in category
        for path, info in items:
            # Use the normalized path from info if available
            display_path = info.get('path', path)
            
            frame = ttk.Frame(cat_frame)
            frame.pack(fill=tk.X, pady=2)
            
            if info['type'] == 'file':
                # Simple checkbox for files
                var = tk.BooleanVar(value=self._guess_default(display_path))
                self.import_vars[display_path] = var
                ttk.Checkbutton(frame, text=f"Include {info['filename']}", 
                               variable=var).pack(anchor=tk.W)
                
            elif info['type'] == 'directory':
                # Directory with options
                if info.get('contents'):
                    self.create_directory_options(frame, display_path, info['contents'])
                else:
                    # Empty directory or couldn't fetch contents
                    ttk.Label(frame, text="Could not fetch directory contents", 
                             foreground='red').pack(anchor=tk.W)
                    var = tk.BooleanVar(value=False)
                    self.import_vars[display_path] = var
        
    def create_directory_options(self, parent, dir_path, contents):
        """Create options for directory imports."""
        # Radio buttons for directory handling
        var = tk.StringVar(value="all")
        self.import_vars[dir_path] = var
        
        ttk.Radiobutton(parent, text="Include all files", 
                       variable=var, value="all").pack(anchor=tk.W)
        ttk.Radiobutton(parent, text="Select specific files", 
                       variable=var, value="selective").pack(anchor=tk.W)
        ttk.Radiobutton(parent, text="Exclude all", 
                       variable=var, value="none").pack(anchor=tk.W)
        
        # Frame for file selections
        files_frame = ttk.Frame(parent)
        files_frame.pack(fill=tk.X, padx=(20, 0), pady=(10, 0))
        
        # Create checkboxes for individual files in columns
        file_vars = {}
        col = 0
        row = 0
        max_cols = 3  # Show files in 3 columns
        
        for item in sorted(contents, key=lambda x: x['name']):
            file_var = tk.BooleanVar(value=False)
            file_vars[item['path']] = file_var
            cb = ttk.Checkbutton(files_frame, text=item['name'], variable=file_var)
            cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        self.directory_selections[dir_path] = file_vars
        
        # Add select all/none buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=(20, 0), pady=(5, 0))
        
        def select_all():
            for file_var in file_vars.values():
                file_var.set(True)
                
        def select_none():
            for file_var in file_vars.values():
                file_var.set(False)
        
        ttk.Button(button_frame, text="Select All", command=select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Select None", command=select_none).pack(side=tk.LEFT, padx=2)
        
        # Enable/disable file checkboxes based on radio selection
        def update_files_state(*args):
            state = tk.NORMAL if var.get() == "selective" else tk.DISABLED
            for widget in files_frame.winfo_children():
                if isinstance(widget, ttk.Checkbutton):
                    widget.configure(state=state)
            for widget in button_frame.winfo_children():
                widget.configure(state=state)
        
        var.trace_add('write', update_files_state)
        update_files_state()  # Initial state
        
    def populate_settings(self):
        """Populate settings from NXP manifest."""
        nxp_config = self.explorer.get_all_configuration()
        
        # Update group filters
        filters = nxp_config.get('group-filter', [])
        if filters:
            self.group_filters_text.delete(1.0, tk.END)
            self.group_filters_text.insert(1.0, '\n'.join(filters))
            
    def _guess_default(self, path):
        """Guess sensible defaults for paths."""
        # Always include base files
        if 'base.yml' in path or 'internal.yml' in path:
            return True
        # Include RTOS by default
        if 'rtos' in path:
            return True
        # Don't include specific device files by default
        if 'devices/' in path and path.endswith('.yml'):
            return False
        # Include middleware directories by default (user can customize)
        if 'middleware/' in path and path.endswith('/'):
            return True
        return False
        
    def update_preview(self):
        """Update the preview with current configuration."""
        try:
            # Build config from UI
            self.build_config_from_ui()
            
            # Generate manifest
            manifest = self.generate_manifest_dict()
            
            # Convert to YAML
            yaml_content = yaml.dump(manifest, default_flow_style=False, sort_keys=False, width=120)
            
            # Add header
            header = f"""# Auto-generated West manifest
# Generated at: {datetime.now().isoformat()}
# Configuration: Custom selection

"""
            
            # Update preview
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, header + yaml_content)
            
            self.status_var.set("Preview updated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate preview: {str(e)}")
            
    def copy_preview(self):
        """Copy preview content to clipboard."""
        content = self.preview_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("Copied to clipboard!")
        
    def build_config_from_ui(self):
        """Build configuration from UI state."""
        self.config = ManifestConfig()
        
        # Settings
        self.config.use_nxp_remotes = self.use_remotes_var.get()
        self.config.use_nxp_defaults = self.use_defaults_var.get()
        self.config.use_nxp_west_commands = self.use_commands_var.get()
        
        # Group filters
        filters_text = self.group_filters_text.get(1.0, tk.END).strip()
        if filters_text:
            self.config.group_filters = [f.strip() for f in filters_text.split('\n') if f.strip()]
        
        # Imports
        self.config.imports = {}
        for path, var in self.import_vars.items():
            if isinstance(var, tk.BooleanVar):
                self.config.imports[path] = var.get()
            elif isinstance(var, tk.StringVar):
                mode = var.get()
                if mode == "all":
                    self.config.imports[path] = True
                elif mode == "none":
                    self.config.imports[path] = False
                elif mode == "selective":
                    # Get selected files
                    selected = []
                    if path in self.directory_selections:
                        for file_path, file_var in self.directory_selections[path].items():
                            if file_var.get():
                                selected.append(file_path)
                    self.config.imports[path] = selected
                    
        self.config.nxp_manifest_url = self.explorer.manifest_url
        
    def generate_manifest_dict(self):
        """Generate manifest dictionary from configuration."""
        manifest = {'manifest': {}}
        m = manifest['manifest']
        
        if hasattr(self.explorer, 'manifest') and self.explorer.manifest:
            nxp_config = self.explorer.get_all_configuration()
            
            # Copy configuration based on settings
            if self.config.use_nxp_remotes and nxp_config.get('remotes'):
                m['remotes'] = nxp_config['remotes']
            
            if self.config.use_nxp_defaults and nxp_config.get('defaults'):
                m['defaults'] = nxp_config['defaults']
            
            if self.config.group_filters:
                m['group-filter'] = self.config.group_filters
            
            # Self configuration
            m['self'] = {}
            if 'path' in nxp_config.get('self', {}):
                m['self']['path'] = nxp_config['self']['path']
            
            if self.config.use_nxp_west_commands and nxp_config.get('self', {}).get('west-commands'):
                m['self']['west-commands'] = nxp_config['self']['west-commands']
            
            # Build imports
            imports = []
            for path, value in self.config.imports.items():
                if isinstance(value, bool):
                    if value:
                        imports.append(path)
                elif isinstance(value, list):
                    imports.extend(value)
            
            # Projects
            m['projects'] = [{
                'name': 'mcuxsdk-manifests',
                'remote': m.get('defaults', {}).get('remote', 'nxp-mcuxpresso'),
                'revision': 'main',
                'import': imports
            }]
        
        return manifest
        
    def save_config(self):
        """Save current configuration to file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.build_config_from_ui()
                
                # Convert to dict for JSON
                config_dict = {
                    'imports': self.config.imports,
                    'group_filters': self.config.group_filters,
                    'use_nxp_remotes': self.config.use_nxp_remotes,
                    'use_nxp_defaults': self.config.use_nxp_defaults,
                    'use_nxp_west_commands': self.config.use_nxp_west_commands,
                    'created_at': self.config.created_at,
                    'nxp_manifest_revision': self.config.nxp_manifest_revision,
                    'nxp_manifest_url': self.config.nxp_manifest_url
                }
                
                with open(filename, 'w') as f:
                    json.dump(config_dict, f, indent=2)
                    
                self.status_var.set(f"Configuration saved to {filename}")
                messagebox.showinfo("Success", "Configuration saved successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
                
    def load_config(self):
        """Load configuration from file."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                self.config = ManifestConfig(**data)
                
                # TODO: Update UI from loaded config
                # This would require reverse-mapping the config to UI state
                
                self.status_var.set(f"Configuration loaded from {filename}")
                messagebox.showinfo("Success", "Configuration loaded! Update preview to see changes.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
                
    def generate_manifest(self):
        """Generate and save the manifest file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".yml",
            filetypes=[("YAML files", "*.yml"), ("All files", "*.*")],
            initialfile="west.yml"
        )
        
        if filename:
            try:
                # Get current preview content
                content = self.preview_text.get(1.0, tk.END).strip()
                
                if not content or content.startswith("Load NXP"):
                    # Generate fresh
                    self.update_preview()
                    content = self.preview_text.get(1.0, tk.END).strip()
                
                with open(filename, 'w') as f:
                    f.write(content)
                    
                self.status_var.set(f"Manifest saved to {filename}")
                messagebox.showinfo("Success", f"Manifest generated successfully!\nSaved to: {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save manifest: {str(e)}")


def main():
    root = tk.Tk()
    app = ManifestConfiguratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()