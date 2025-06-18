import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import sys # Added for resource_path
import json
from ttkthemes import ThemedTk

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not frozen, or _MEIPASS not available.
        # In development, __file__ is in src/, and icon.png is also in src/
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class ReplayConverterApp:
    """
    A GUI application for LMI's ReplayConverter.exe tool with an improved visual design.
    """
    APP_NAME = "ReplayConverterGUI"
    SETTINGS_FILENAME = "replay_converter_settings.json"

    def __init__(self, root):
        """
        Initializes the main application window.
        Args:
            root: The root ThemedTk window.
        """
        self.root = root
        self.root.title("Replay Converter UI")
        self.root.geometry("700x600")
        self.root.minsize(650, 480)

        # Set application icon
        try:
            # Use resource_path to find icon.png correctly in dev and frozen states
            # "icon.png" is the relative path from base_path (src/ for dev, _MEIPASS/ for frozen)
            icon_path_resolved = resource_path("icon.png")
            if os.path.exists(icon_path_resolved):
                self.app_icon = tk.PhotoImage(file=icon_path_resolved) # Keep a reference
                self.root.iconphoto(True, self.app_icon)
            else:
                print(f"Warning: Application icon 'icon.png' not found at resolved path: {icon_path_resolved}")
        except tk.TclError as e:
            # Handle cases where the icon format might not be supported or other Tk errors
            print(f"Warning: Could not set application icon: {e}")
        except Exception as e: # Catch other potential errors during icon loading
            print(f"An unexpected error occurred while setting application icon: {e}")

        # --- Instance Variables ---
        self.command_parts = []
        # Determine and set up the settings file path
        self.app_data_dir = os.path.join(os.path.expanduser("~"), f".{self.APP_NAME}")
        self.settings_file_path = os.path.join(self.app_data_dir, self.SETTINGS_FILENAME)
        self.settings = self.load_settings()

        self._processing_output_entry_change = False # Flag to prevent recursion

        # --- Style Configuration ---
        self.setup_styles()

        # --- Main Frame ---
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill='both')

        # --- Input File Section ---
        input_frame = ttk.LabelFrame(main_frame, text="1. Select Input File", padding=(15, 10))
        input_frame.pack(fill='x', pady=(0, 15))
        input_frame.columnconfigure(0, weight=1)

        self.input_file_var = tk.StringVar()
        self.input_file_entry = ttk.Entry(input_frame, textvariable=self.input_file_var, state='readonly')
        self.input_file_entry.grid(row=0, column=0, sticky='ew', padx=(0, 10), ipady=4)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_input_file)
        self.browse_button.grid(row=0, column=1)

        # --- Options Section ---
        options_frame = ttk.LabelFrame(main_frame, text="2. Configure Options", padding=(15, 10))
        options_frame.pack(fill='x', pady=15)
        # Configure column weights for proper expansion
        options_frame.columnconfigure(1, weight=1)
        # Column 2 for browse button / frame index label, Column 3 for frame index entry (no weight needed for these)

        # Output Format
        ttk.Label(options_frame, text="Output Format:").grid(row=0, column=0, sticky='w', padx=(0, 10), pady=5)
        self.output_format_var = tk.StringVar(value='.srf')
        self.output_format_dropdown = ttk.Combobox(
            options_frame,
            textvariable=self.output_format_var,
            values=['.gprec', '.srf', '.sur', '.pcd', '.pro', '.csv'],
            state='readonly'
        )
        self.output_format_dropdown.grid(row=0, column=1, sticky='ew', pady=5)
        self.output_format_dropdown.bind("<<ComboboxSelected>>", self.update_command_display)

        # Frame Export
        self.export_all_var = tk.BooleanVar(value=True)
        self.export_all_check = ttk.Checkbutton(options_frame, text="Export all frames (-a)",
                                                variable=self.export_all_var, command=self.toggle_frame_entry)
        self.export_all_check.grid(row=1, column=0, sticky='w', pady=5)

        ttk.Label(options_frame, text="Frame Index (-f):").grid(row=1, column=2, sticky='e', padx=(20, 10), pady=5)
        self.frame_index_var = tk.StringVar(value="0")
        self.frame_index_entry = ttk.Entry(options_frame, textvariable=self.frame_index_var, width=15)
        self.frame_index_entry.grid(row=1, column=3, sticky='ew', pady=5)
        self.frame_index_entry.bind("<KeyRelease>", self.update_command_display)

        # Output File Name
        ttk.Label(options_frame, text="Output Name:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(15, 5))
        self.output_file_var = tk.StringVar()
        self.output_file_entry = ttk.Entry(options_frame, textvariable=self.output_file_var) 
        self.output_file_entry.grid(row=2, column=1, sticky='ew', pady=(15, 5), ipady=2) # Entry takes available space
        self.output_file_entry.bind("<KeyRelease>", self.handle_output_file_entry_change)

        self.browse_output_button = ttk.Button(options_frame, text="Browse...", command=self.browse_output_file, width=10)
        self.browse_output_button.grid(row=2, column=2, sticky='e', padx=(5,0), pady=(15,5))


        # --- Command Preview Section ---
        command_frame = ttk.LabelFrame(main_frame, text="3. Review Command", padding=(15, 10))
        command_frame.pack(expand=True, fill='both', pady=15)
        
        self.command_text = tk.Text(command_frame, height=3, wrap='word',
                                    font=("Courier New", 10), relief='solid', borderwidth=1,
                                    background="#FFFFFF", foreground="#333333", state='disabled',
                                    padx=10, pady=10)
        self.command_text.pack(expand=True, fill='both')
        self.command_text.tag_configure("error", foreground="red")

        # --- Action Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', side='bottom', pady=(10, 0))
        
        self.settings_button = ttk.Button(button_frame, text="Settings", command=self.open_settings)
        self.settings_button.pack(side='left')

        self.quit_button = ttk.Button(button_frame, text="Quit", command=self.root.quit)
        self.quit_button.pack(side='right')
        
        self.run_button = ttk.Button(button_frame, text="Convert", command=self.run_conversion, style="Accent.TButton")
        self.run_button.pack(side='right', padx=10)

        # --- Initial State ---
        self.toggle_frame_entry()
        self.update_command_display()

    def setup_styles(self):
        """Configures the visual styles for the application widgets."""
        style = ttk.Style(self.root)
        font_body = ('Segoe UI', 10)
        font_label = ('Segoe UI', 11, 'bold')

        style.configure('.', font=font_body, foreground='#212121')
        style.configure('TLabel', font=font_body)
        style.configure('TButton', padding=8, width=12)
        style.configure('TLabelFrame', padding=10)
        style.configure('TLabelFrame.Label', font=font_label, foreground='#00529B')
        
        # Style the Combobox dropdown list
        # The main TCombobox widget generally follows the theme, but the dropdown list (a Listbox)
        # often needs explicit option_add for consistent styling.
        self.root.option_add('*TCombobox*Listbox.font', font_body)
        self.root.option_add('*TCombobox*Listbox.background', '#FFFFFF') # Use a light background
        self.root.option_add('*TCombobox*Listbox.foreground', '#212121') # Standard text color
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#0078D4') # Accent color for selection
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')    # White text for selection

        # Create a custom element for the accent button
        try:
            style.element_create("accent.button.border", "from", "default")
            style.element_create("accent.button.focus", "from", "default")
            style.element_create("accent.button.padding", "from", "default")
            style.element_create("accent.button.label", "from", "default")
        except tk.TclError:
            pass  # Elements might already exist
        
        # Configure the accent button layout
        style.layout('Accent.TButton', [
            ('accent.button.border', {'sticky': 'nswe', 'border': '1', 'children': [
                ('accent.button.focus', {'sticky': 'nswe', 'children': [
                    ('accent.button.padding', {'sticky': 'nswe', 'children': [
                        ('accent.button.label', {'sticky': 'nswe'})
                    ]})
                ]})
            ]})
        ])
        
        # Force the accent button style with stronger configuration
        style.configure('Accent.TButton',
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=1,
                        focuscolor='none',
                        darkcolor='#0078D4',
                        lightcolor='#0078D4',
                        bordercolor='#0078D4',
                        selectbackground='#0078D4',
                        selectforeground='white')
        
        # Use element options to force colors with higher priority
        style.map('Accent.TButton',
                  background=[('active', '#005A9E'),
                              ('pressed', '#004578'),
                              ('selected', '#0078D4'),
                              ('!disabled', '#0078D4')],
                  foreground=[('active', 'white'),
                              ('pressed', 'white'),
                              ('selected', 'white'),
                              ('!disabled', 'white')],
                  relief=[('pressed', 'flat'),
                          ('!pressed', 'flat')],
                  bordercolor=[('active', '#005A9E'),
                               ('pressed', '#004578'),
                               ('!disabled', '#0078D4')],
                  darkcolor=[('!disabled', '#0078D4')],
                  lightcolor=[('!disabled', '#0078D4')])

    def _get_default_settings(self):
        """Returns a dictionary with default settings."""
        return {
            "converter_path": "",
            "pcd_width": "0",
            "pcd_height": "0",
            "pcd_swap": False,
            "pcd_zoom": "1.0",
            "pcd_remove": False
        }

    def load_settings(self):
        """Loads settings from JSON, returns defaults if not found."""
        default_settings = self._get_default_settings()
        # Ensure the application data directory exists
        if not os.path.exists(self.app_data_dir):
            try:
                os.makedirs(self.app_data_dir)
            except OSError as e:
                print(f"Warning: Could not create settings directory {self.app_data_dir}: {e}")
                # Fallback to default settings if directory creation fails,
                # but still attempt auto-detection below.
                settings = default_settings.copy() # Make a copy to modify
                # Auto-detection logic will run on this copy.

        # Initialize settings with defaults, then try to load and update
        settings = default_settings.copy()
        try:
            with open(self.settings_file_path, 'r') as f:
                loaded_settings = json.load(f)
                # Merge loaded settings with defaults to ensure all keys are present
                settings.update(loaded_settings)
        except (FileNotFoundError, json.JSONDecodeError):
            # File not found or invalid JSON, return defaults. File will be created on first save.
            # 'settings' remains as default_settings.
            pass
        except Exception as e:
            print(f"Warning: Error loading settings file {self.settings_file_path}: {e}")
            # 'settings' remains as default_settings in case of other errors.
            pass

        # --- Auto-populate converter_path if empty and ReplayConverter.exe is found locally ---
        if not settings.get("converter_path"): # Check if path is empty or not set
            try:
                local_converter_exe = "ReplayConverter.exe"
                potential_path = resource_path(local_converter_exe)
                if os.path.isfile(potential_path):
                    settings["converter_path"] = potential_path
                    print(f"INFO: Auto-detected and set ReplayConverter.exe path: {potential_path}")
            except Exception as e:
                print(f"DEBUG: Error during auto-detection of ReplayConverter.exe: {e}")
        
        return settings

    def save_settings(self):
        """Saves current settings to the JSON file."""
        if not os.path.exists(self.app_data_dir):
            try:
                os.makedirs(self.app_data_dir)
            except OSError as e:
                messagebox.showerror("Error", f"Could not create settings directory:\n{self.app_data_dir}\n\nSettings not saved.")
                return
        with open(self.settings_file_path, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def browse_input_file(self):
        """Opens a file dialog to select an input file."""
        file_path = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=(("All Supported", "*.gprec *.srf *.sur *.pcd *.pro"),
                       ("GoPxL Recording", "*.gprec"), ("Surface", "*.srf *.sur *.pcd"),
                       ("Profile", "*.pro"), ("All files", "*.*"))
        )
        if file_path:
            self.input_file_var.set(file_path)
            path, filename = os.path.split(file_path)
            name, _ = os.path.splitext(filename)
            self.output_file_var.set(os.path.join(path, name))
            self.update_command_display()

    def browse_output_file(self):
        """Opens a save dialog to select an output file name and location."""
        # Determine initial directory and filename for the dialog
        current_output_file_base = self.output_file_var.get() # This is path + name_no_ext
        input_file_path = self.input_file_var.get()
        current_selected_ext = self.output_format_var.get() # Get current format from dropdown

        if current_output_file_base:
            # If output entry has content, use its directory and base name
            initial_dir = os.path.dirname(current_output_file_base)
            suggested_name_part = os.path.basename(current_output_file_base)
        elif input_file_path:
            # If output is empty but input exists, use input's dir and base name
            initial_dir = os.path.dirname(input_file_path)
            suggested_name_part = os.path.splitext(os.path.basename(input_file_path))[0]
        else:
            # Both empty, use current working directory and a default name
            initial_dir = os.getcwd()
            suggested_name_part = "output" # Default suggestion

        initial_file_suggestion = f"{suggested_name_part}{current_selected_ext}"

        available_extensions = self.output_format_dropdown['values']
        file_types_for_dialog = []


        # Add the currently selected format first to make it the default in the dialog's type dropdown
        if current_selected_ext in available_extensions:
            file_types_for_dialog.append((f"{current_selected_ext.upper().replace('.', '')} File", f"*{current_selected_ext}"))

        # Add other available extensions, ensuring no duplicates with the first one
        for ext_val in available_extensions:
            if ext_val != current_selected_ext:
                file_types_for_dialog.append((f"{ext_val.upper().replace('.', '')} File", f"*{ext_val}"))
        file_types_for_dialog.append(("All files", "*.*"))

        chosen_path = filedialog.asksaveasfilename(
            title="Select Output File",
            initialdir=initial_dir,
            initialfile=initial_file_suggestion, # Use the generated suggestion (name.ext)
            defaultextension=current_selected_ext, # Ensure this matches the initial file's extension
            filetypes=file_types_for_dialog
        )

        if chosen_path:
            base, ext = os.path.splitext(chosen_path)
            ext = ext.lower()

            self.output_file_var.set(base) # Set the base name to the entry

            if ext and ext in [e.lower() for e in available_extensions]:
                if self.output_format_var.get() != ext:
                    self.output_format_var.set(ext)
            
            # Always update the command display after processing the chosen path.
            # This ensures that changes to the base name (from self.output_file_var.set(base))
            # and potential changes to the format (from self.output_format_var.set(ext)) are reflected.
            self.update_command_display()

    def toggle_frame_entry(self):
        """Enables/disables the frame index entry."""
        self.frame_index_entry.config(state='disabled' if self.export_all_var.get() else 'normal')
        self.update_command_display()

    def handle_output_file_entry_change(self, event=None):
        """Handles KeyRelease in output file entry to update format dropdown and entry text."""
        if self._processing_output_entry_change: # Prevent recursion
            return
        self._processing_output_entry_change = True

        current_text = self.output_file_var.get()
        base, ext_typed = os.path.splitext(current_text)
        original_ext_case = ext_typed # Preserve original case for comparison
        ext_typed_lower = ext_typed.lower()
        
        valid_formats = [f.lower() for f in self.output_format_dropdown['values']]
        
        format_changed_by_typing = False

        if ext_typed_lower and ext_typed_lower in valid_formats:
            # User typed a valid extension
            if self.output_format_var.get() != ext_typed_lower:
                self.output_format_var.set(ext_typed_lower) # This updates dropdown and triggers its own update_command_display
                format_changed_by_typing = True
            
            # Update the entry to show only the base name, if it contained the extension
            if current_text.lower().endswith(ext_typed_lower): # Check if entry actually had the extension
                # Use after_idle to ensure Tkinter processes the current event loop
                # before changing the variable that triggered this event.
                self.output_file_entry.after_idle(lambda: self.output_file_var.set(base))
        
        if not format_changed_by_typing:
            # If format wasn't changed by typing (e.g. user just edited base name, or typed invalid ext)
            # we still need to update the command preview.
            self.update_command_display()
        
        self._processing_output_entry_change = False

    def update_command_display(self, event=None):
        """Builds the command for execution and updates the preview text area."""
        error_messages = [] 

        converter_path_val = self.settings.get("converter_path")
        input_file_val = self.input_file_var.get()
        output_file_base_val = self.output_file_var.get()
        output_format_val = self.output_format_dropdown.get()

        # --- Determine PCD arguments if applicable ---
        pcd_args = []
        if output_format_val == '.pcd':
            pcd_width = self.settings.get('pcd_width', '0')
            pcd_height = self.settings.get('pcd_height', '0')
            pcd_swap = self.settings.get('pcd_swap', False)
            pcd_zoom = self.settings.get('pcd_zoom', '1.0')
            pcd_remove = self.settings.get('pcd_remove', False)

            if pcd_width != '0': pcd_args.extend(("-w", pcd_width))
            if pcd_height != '0': pcd_args.extend(("-h", pcd_height))
            if pcd_swap: pcd_args.append("-s")
            if pcd_zoom != '1.0': pcd_args.extend(("-z", pcd_zoom))
            if pcd_remove: pcd_args.append("-r")

        # --- Build parts for DISPLAY PREVIEW ---
        display_parts_for_preview = []
        if converter_path_val:
            display_parts_for_preview.append(converter_path_val)
        else:
            display_parts_for_preview.append("[CONVERTER_PATH]")
            error_messages.append("Error: Path to ReplayConverter.exe is not set. Please go to Settings.")

        # Input File
        if input_file_val:
            display_parts_for_preview.extend(['-i', input_file_val])
        else:
            display_parts_for_preview.extend(['-i', '[INPUT_FILE]'])
            error_messages.append("Error: Please select an input file.")

        # Export All / Frame Index
        if self.export_all_var.get():
            display_parts_for_preview.append('-a')
        else:
            frame_index_val = self.frame_index_var.get()
            display_parts_for_preview.extend(['-f', frame_index_val if frame_index_val else '[FRAME_INDEX]'])
            if not frame_index_val:
                 error_messages.append("Warning: Frame index is empty when 'Export all frames' is unchecked.")

        # Output File Name and Format
        if output_file_base_val:
            display_parts_for_preview.extend(['-o', f"{output_file_base_val}{output_format_val}"])
        else:
            display_parts_for_preview.extend(['-o', f"[OUTPUT_NAME]{output_format_val}"])
            error_messages.append("Warning: Output file name is not specified.")

        # Add PCD arguments to preview
        display_parts_for_preview.extend(pcd_args)

        # Generate the display string, quoting paths for readability
        quoted_display_list = []
        for i, part in enumerate(display_parts_for_preview):
            # Quote the executable path and paths after -i or -o
            if i == 0 or (i > 0 and display_parts_for_preview[i-1] in ['-i', '-o']):
                quoted_display_list.append(f'"{part}"')
            else:
                quoted_display_list.append(part)
        command_display_str = " ".join(quoted_display_list)

        self.command_text.config(state='normal')
        self.command_text.delete('1.0', tk.END)
        self.command_text.insert('1.0', command_display_str)
        if error_messages:
            self.command_text.insert(tk.END, f"\n" + "\n".join(error_messages), "error")
        
        # --- Build self.command_parts for EXECUTION (re-use validated values) ---
        self.command_parts = [] 
        if converter_path_val and input_file_val: # Critical parts must be present
            self.command_parts.append(converter_path_val)
            self.command_parts.extend(['-i', input_file_val])

            if self.export_all_var.get():
                self.command_parts.append('-a')
            else:
                frame_index_val_exec = self.frame_index_var.get()
                if frame_index_val_exec: # Basic check, could add isdigit validation
                    self.command_parts.extend(['-f', frame_index_val_exec])
                else:
                    self.command_parts = [] # Invalidate command for execution

            # Only add output and PCD options if command is still valid and output name is provided
            if self.command_parts: # Check if still valid after primary args
                if output_file_base_val:
                    self.command_parts.extend(['-o', f"{output_file_base_val}{output_format_val}"])
                else:
                    self.command_parts = [] # Output name is crucial for execution

                if self.command_parts: # Check if still valid after output option
                    self.command_parts.extend(pcd_args) # Add PCD args to execution command
        else: # Critical parts (converter path or input file) were missing
            self.command_parts = []

        self.command_text.config(state='disabled')

    def run_conversion(self):
        """Executes the generated command in a subprocess using the command_parts list."""
        if not self.command_parts:
            messagebox.showerror("Error", "No command to execute. Please check your inputs and settings.")
            return
        if not os.path.exists(self.command_parts[0]):
            messagebox.showerror("Error", f"Converter not found at: {self.command_parts[0]}\nPlease check the path in Settings.")
            return

        try:
            command_string_for_display = self.command_text.get("1.0", tk.END).strip()
            messagebox.showinfo("Running", f"Executing command:\n\n{command_string_for_display}")
            
            # Use self.command_parts directly for a robust call
            process = subprocess.run(self.command_parts, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            output_message = f"Conversion Successful!"
            if process.stdout:
                output_message += f"\n\nOutput:\n{process.stdout}"
            if process.stderr:
                output_message += f"\n\nWarnings:\n{process.stderr}"
            messagebox.showinfo("Success", output_message)

        except subprocess.CalledProcessError as e:
            error_message = f"Conversion Failed!\n\nReturn Code: {e.returncode}\n\nError:\n{e.stderr}"
            messagebox.showerror("Error", error_message)
        except Exception as e:
            messagebox.showerror("An Unexpected Error Occurred", str(e))

    def open_settings(self):
        """Opens the modal settings window."""
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("550x400")
        self.settings_window.transient(self.root)
        self.settings_window.grab_set()
        
        # Styles are inherited from the root window, including ThemedTk theme
        # and custom styles like 'Accent.TButton' defined in setup_styles.
        settings_frame = ttk.Frame(self.settings_window, padding="20")
        settings_frame.pack(expand=True, fill='both')

        path_frame = ttk.LabelFrame(settings_frame, text="ReplayConverter.exe Path", padding=10)
        path_frame.pack(fill='x', pady=(0, 15))
        path_frame.columnconfigure(0, weight=1)

        self.converter_path_var = tk.StringVar(value=self.settings.get("converter_path", ""))
        ttk.Entry(path_frame, textvariable=self.converter_path_var, state='readonly').grid(row=0, column=0, sticky='ew', padx=(0, 10), ipady=4)
        ttk.Button(path_frame, text="Browse...", command=self.browse_converter_path).grid(row=0, column=1)

        pcd_frame = ttk.LabelFrame(settings_frame, text="PCD Import Defaults", padding=10)
        pcd_frame.pack(fill='x', pady=15)

        ttk.Label(pcd_frame, text="Width (-w):").grid(row=0, column=0, sticky='w', pady=4)
        self.pcd_width_var = tk.StringVar(value=self.settings.get('pcd_width', "0"))
        ttk.Entry(pcd_frame, textvariable=self.pcd_width_var, width=10).grid(row=0, column=1, sticky='w', pady=4)
        
        ttk.Label(pcd_frame, text="Height (-h):").grid(row=1, column=0, sticky='w', pady=4)
        self.pcd_height_var = tk.StringVar(value=self.settings.get('pcd_height', "0"))
        ttk.Entry(pcd_frame, textvariable=self.pcd_height_var, width=10).grid(row=1, column=1, sticky='w', pady=4)
        
        ttk.Label(pcd_frame, text="Zoom (-z):").grid(row=2, column=0, sticky='w', pady=4)
        self.pcd_zoom_var = tk.StringVar(value=self.settings.get('pcd_zoom', "1.0"))
        ttk.Entry(pcd_frame, textvariable=self.pcd_zoom_var, width=10).grid(row=2, column=1, sticky='w', pady=4)

        self.pcd_swap_var = tk.BooleanVar(value=self.settings.get('pcd_swap', False))
        ttk.Checkbutton(pcd_frame, text="Swap X/Z (-s)", variable=self.pcd_swap_var).grid(row=0, column=2, sticky='w', padx=30)
        
        self.pcd_remove_var = tk.BooleanVar(value=self.settings.get('pcd_remove', False))
        ttk.Checkbutton(pcd_frame, text="Remove specific point (-r)", variable=self.pcd_remove_var).grid(row=1, column=2, sticky='w', padx=30)

        btn_frame = ttk.Frame(settings_frame)
        btn_frame.pack(fill='x', side='bottom', pady=(10, 0))
        
        ttk.Button(btn_frame, text="Cancel", command=self.settings_window.destroy).pack(side='right')
        ttk.Button(btn_frame, text="Save", command=self.save_and_close_settings, style='Accent.TButton').pack(side='right', padx=10)

    def browse_converter_path(self):
        """Opens a file dialog to select the ReplayConverter.exe."""
        file_path = filedialog.askopenfilename(
            title="Select ReplayConverter.exe", filetypes=(("Executable", "*.exe"), ("All files", "*.*"))
        )
        if file_path:
            self.converter_path_var.set(file_path)

    def save_and_close_settings(self):
        """Saves settings and closes the settings window."""
        self.settings["converter_path"] = self.converter_path_var.get()
        self.settings["pcd_width"] = self.pcd_width_var.get()
        self.settings["pcd_height"] = self.pcd_height_var.get()
        self.settings["pcd_swap"] = self.pcd_swap_var.get()
        self.settings["pcd_zoom"] = self.pcd_zoom_var.get()
        self.settings["pcd_remove"] = self.pcd_remove_var.get()
        
        self.save_settings()
        messagebox.showinfo("Saved", f"Settings have been saved to:\n{self.settings_file_path}", parent=self.settings_window)
        self.settings_window.destroy()
        self.update_command_display()

if __name__ == '__main__':
    # Use ThemedTk to apply a modern theme
    root = ThemedTk(theme="arc")
    app = ReplayConverterApp(root)
    root.mainloop()