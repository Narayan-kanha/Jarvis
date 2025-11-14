import os
import sys

def get_language_from_extension(file_extension):
    """
    Returns the programming language based on its file extension.
    This map is comprehensive to handle a wide variety of code.
    """
    # Normalize extension to lowercase and include the dot
    ext = '.' + file_extension.lower().lstrip('.')
    
    extension_map = {
        # Assembly
        '.asm': 'Assembly',
        '.s': 'Assembly',

        # C/C++ Family
        '.c': 'C',
        '.h': 'C/C++ Header',
        '.cpp': 'C++',
        '.hpp': 'C++ Header',
        '.cs': 'C#',
        '.m': 'Objective-C',

        # Python

        '.py': 'Python',
        '.pyw': 'Python',

        # Java/JVM
        '.java': 'Java',
        '.kt': 'Kotlin',
        '.kts': 'Kotlin Script',
        '.groovy': 'Groovy',
        '.scala': 'Scala',

        # Web Development

        '.js': 'JavaScript',
        '.mjs': 'JavaScript Module',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript React',

        '.html': 'HTML',
        '.css': 'CSS',
        '.php': 'PHP',
        '.xml': 'XML',

        # Shell/Scripting
        '.sh': 'Shell Script',
        '.bash': 'Bash',
        '.ps1': 'PowerShell',
        '.pl': 'Perl',
        '.rb': 'Ruby',
        '.lua': 'Lua',
        
        # Functional Languages
        '.hs': 'Haskell',
        '.lisp': 'Lisp',
        '.clj': 'Clojure',
        '.fs': 'F#',
        '.ml': 'OCaml',
        
        # Systems Languages
        '.go': 'Go',
        '.rs': 'Rust',
        '.swift': 'Swift',
        '.d': 'D',
        '.nim': 'Nim',
        
        # DevOps/Data
        '.sql': 'SQL',
        '.r': 'R',
        '.dart': 'Dart',
        '.ex': 'Elixir',
        '.exs': 'Elixir Script',
        '.erl': 'Erlang',
        
        # Others
        '.pas': 'Pascal',
        '.f90': 'Fortran',
        '.f': 'Fortran',
        '.v': 'Verilog',
        '.vhd': 'VHDL',
        '.vb': 'Visual Basic',
        '.rkt': 'Racket',
        '.cmake': 'CMake',
        '.txt': 'Text',
        '.md': 'Markdown',
    }
    return extension_map.get(ext) # Returns None if not a recognized code extension

def extract_code(source_dir, output_dir, max_lines_per_file=100000):
    """
    Extracts code from a source directory and saves it into multiple text files 
    in an output directory, each with a maximum line count.
    """
    # Extensions to explicitly ignore (case-insensitive)
    excluded_extensions = {
        # Binary / Compiled
        '.bin', '.dll', '.exe', '.so', '.o', '.a', '.lib',
        # Data / Models
        '.pth', '.pkl', '.dat', '.db', '.sqlite3', '.csv', '.json', '.yaml', '.yml',
        # Documents / Text
        '.log', '.rtf', '.pdf', '.doc', '.docx',
        # Archives
        '.zip', '.tar', '.gz', '.rar', '.7z',
        # Images
        '.png', 'jpeg', '.jpg', '.gif', '.bmp', '.svg',
        # Version Control & Config
        '.git', '.gitignore', '.gitattributes', '.lock',
        # Other common non-source files
        '.classpath', '.project', '.settings', '.ds_store'
    }

    # --- Setup ---
    # Ensure source directory exists before starting
    if not os.path.isdir(source_dir):
        print(f"Error: The source directory '{source_dir}' was not found.")
        print(f"Please make sure your code is inside a folder named '{source_dir}' in the same directory as the script.")
        sys.exit() # Exit the script if the source folder isn't there

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    total_files_processed = 0
    output_file_count = 1
    current_line_count = 0
    
    # Define the initial output file
    output_filepath = os.path.join(output_dir, f"extracted_code_part_{output_file_count}.txt")
    current_output_file = open(output_filepath, "w", encoding="utf-8", errors='ignore')
    print(f"Starting extraction. Writing to {output_filepath}...")

    # --- Main Loop ---
    for root, _, filenames in os.walk(source_dir):
        for filename in filenames:
            # Get file extension and check if it should be excluded
            _, file_extension = os.path.splitext(filename)
            if not file_extension or file_extension.lower() in excluded_extensions:
                continue

            # Identify the language
            language = get_language_from_extension(file_extension)
            if language is None: # Skip if not a recognized code language
                continue

            file_path = os.path.join(root, filename)

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                    code_content = infile.read()
            except Exception as e:
                print(f"Could not read file: {file_path}. Error: {e}")
                continue

            # Use the immediate parent folder as the project name
            project_name = os.path.basename(root)
            total_files_processed += 1

            # Format the output block as requested
            header = f"({project_name})\n\nFile {total_files_processed} - Language - {language}:\n\n"
            output_block = f"{header}<<<<Code>>>>\n{code_content}\n<<<<End Code>>>>\n\n\n"
            
            # --- CRITICAL: File Splitting Logic ---
            lines_in_block = output_block.count('\n')
            if current_line_count + lines_in_block > max_lines_per_file and current_line_count > 0:
                current_output_file.close() # Close the full file
                print(f"Line limit reached. Saved {current_line_count} lines to {output_filepath}.")

                # Create a new file
                output_file_count += 1
                output_filepath = os.path.join(output_dir, f"extracted_code_part_{output_file_count}.txt")
                current_output_file = open(output_filepath, "w", encoding="utf-8", errors='ignore')
                print(f"Now writing to {output_filepath}...")
                current_line_count = 0 # Reset counter for the new file

            # Write to the current file and update the line count
            current_output_file.write(output_block)
            current_line_count += lines_in_block

    # --- Cleanup ---
    current_output_file.close()
    print("\nExtraction complete!")
    print(f"A total of {total_files_processed} code files were processed.")
    print(f"Output saved in {output_file_count} file(s) inside the '{output_dir}' directory.")

# --- Main execution block ---
if __name__ == "__main__":
    # The script now automatically uses folders in its own directory
    # No need to edit any paths!
    
    # 1. Input folder: Must be named 'github_code'
    source_directory_name = "github_code"
    
    # 2. Output folder: Will be created as 'extracted_code'
    destination_directory_name = "extracted_code"
    
    extract_code(source_directory_name, destination_directory_name)