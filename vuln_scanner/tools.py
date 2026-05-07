import os


ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".php", ".rb", ".c", ".cpp"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}


def list_files(target_path: str) -> str:
    """Walk directory tree and return code files only, skipping common non-source directories."""
    if not os.path.isdir(target_path):
        return f"Error: '{target_path}' is not a valid directory."

    results = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in sorted(files):
            if os.path.splitext(fname)[1] in ALLOWED_EXTENSIONS:
                rel = os.path.relpath(os.path.join(root, fname), target_path)
                results.append(rel)

    if not results:
        return "No code files found in the specified directory."
    return "\n".join(results)


def read_file(file_path: str) -> str:
    """Read and return file content, capped at 30 KB."""
    if not os.path.isfile(file_path):
        return f"Error: File '{file_path}' not found."

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(30720)
        if os.path.getsize(file_path) > 30720:
            content += "\n\n[TRUNCATED — file exceeds 30 KB limit]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"
