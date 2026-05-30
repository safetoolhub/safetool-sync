# SafeTool Sync

**SafeTool Sync** is a cross-platform desktop application for mirror synchronization between disks and folders. It helps you keep your files in sync with powerful features like smart comparison, conflict resolution, and multiple sync presets.

---

## English

### Purpose

SafeTool Sync synchronizes files between disks and folders. Whether you're backing up data, mirroring a working directory, or keeping two drives in sync, SafeTool Sync provides:

- **Multiple sync presets**: Mirror Exact, Mirror Safe, Copy Only, Mirror Hash, Two-Way Safe, Two-Way Exact, Two-Way Hash, and Custom
- **Smart comparison**: Detects modified, renamed, and conflicting files using size, modification time, and SHA-256 hashing
- **Conflict resolution**: Choose how to handle conflicts with flexible policies (Source Wins, Keep Destination, or Manual Review)
- **Smart match**: Automatically identifies files that are likely the same but with different names (e.g., `report.pdf` → `report_v2.pdf`)
- **Verification**: Full or spot-check SHA-256 verification after file operations
- **Trash safety**: Optionally send deleted files to trash instead of permanently removing them
- **Snapshots**: Save and resume sync states between sessions

### How to Launch

1. **Install dependencies** (first time only):
   ```bash
   uv sync
   ```

2. **Run the application**:
   ```bash
   uv run python app.py
   ```

For development dependencies, use `uv sync --extra dev`.

### Requirements

- Python 3.12+
- `uv` package manager

---

## Español

### Propósito

SafeTool Sync sincroniza archivos entre discos y carpetas. Ya sea que estés haciendo copias de seguridad, replicando un directorio de trabajo o manteniendo dos unidades sincronizadas, SafeTool Sync ofrece:

- **Múltiples perfiles de sincronización**: Espejo Exacto, Espejo Seguro, Solo Copia, Espejo Hash, Bidireccional Seguro, Bidireccional Exacto, Bidireccional Hash y Personalizado
- **Comparación inteligente**: Detecta archivos modificados, renombrados y en conflicto usando tamaño, fecha de modificación y hash SHA-256
- **Resolución de conflictos**: Elige cómo manejar conflictos con políticas flexibles (Fuente Gana, Mantener Destino o Revisión Manual)
- **Coincidencia inteligente**: Identifica automáticamente archivos que probablemente son el mismo pero con nombres diferentes (ej. `informe.pdf` → `informe_v2.pdf`)
- **Verificación**: Verificación SHA-256 completa o por muestreo después de las operaciones de archivo
- **Seguridad con papelera**: Opcionalmente envía archivos eliminados a la papelera en lugar de borrarlos permanentemente
- **Instantáneas**: Guarda y reanuda estados de sincronización entre sesiones

### Cómo Ejecutar

1. **Instalar dependencias** (solo la primera vez):
   ```bash
   uv sync
   ```

2. **Ejecutar la aplicación**:
   ```bash
   uv run python app.py
   ```

Para dependencias de desarrollo, usa `uv sync --extra dev`.

### Requisitos

- Python 3.12+
- Gestor de paquetes `uv`

---

## License

GPLv3 with attribution — See LICENSE file for details.
