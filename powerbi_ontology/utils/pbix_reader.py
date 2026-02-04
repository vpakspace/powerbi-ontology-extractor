"""
PBIX Reader Utility

Reads Power BI .pbix files using PBIXRay library to parse binary DataModel.
Supports both modern .pbix files (binary DataModel) and legacy files (model.bim JSON).
"""

import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import pbixray for modern .pbix parsing
try:
    from pbixray import PBIXRay
    PBIXRAY_AVAILABLE = True
except ImportError:
    PBIXRAY_AVAILABLE = False
    logger.warning("pbixray not installed. Install with: pip install pbixray")


class PBIXReader:
    """
    Reads Power BI .pbix files and extracts semantic model information.

    Uses PBIXRay library to parse binary DataModel (XPress9 compressed).
    Falls back to JSON model.bim for legacy/export files.

    .pbix files are ZIP archives containing:
    - DataModel (binary, XPress9 compressed) - modern files
    - DataModel/model.bim (JSON) - legacy/exported files
    - Report/Layout (JSON, UTF-16) - report visualizations
    - [DataMashup] - Power Query M code
    """

    def __init__(self, pbix_path: str):
        """
        Initialize PBIX reader.

        Args:
            pbix_path: Path to the .pbix file
        """
        self.pbix_path = Path(pbix_path)
        if not self.pbix_path.exists():
            raise FileNotFoundError(f"Power BI file not found: {pbix_path}")

        self.temp_dir: Optional[Path] = None
        self._pbixray: Optional[Any] = None
        self._model_data: Optional[Dict] = None
        self._use_pbixray: bool = False
        self._tables_cache: Optional[List[Dict]] = None
        self._relationships_cache: Optional[List[Dict]] = None
        self._measures_cache: Optional[List[Dict]] = None

    def __enter__(self):
        """Context manager entry."""
        self.extract_to_temp()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        self.cleanup()

    def extract_to_temp(self) -> Path:
        """
        Extract .pbix file to temporary directory (for legacy support).
        Also initializes PBIXRay if available.

        Returns:
            Path to temporary extraction directory
        """
        if self.temp_dir:
            return self.temp_dir

        # Try PBIXRay first for modern .pbix files
        if PBIXRAY_AVAILABLE:
            try:
                self._pbixray = PBIXRay(str(self.pbix_path))
                # Test if we can read tables
                _ = self._pbixray.tables
                self._use_pbixray = True
                logger.info(f"Using PBIXRay for {self.pbix_path}")
            except Exception as e:
                logger.warning(f"PBIXRay failed, falling back to JSON: {e}")
                self._use_pbixray = False

        # Extract to temp for fallback/additional data
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="pbix_extract_"))

            with zipfile.ZipFile(self.pbix_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)

            logger.info(f"Extracted .pbix file to {self.temp_dir}")
            return self.temp_dir
        except zipfile.BadZipFile:
            raise ValueError(f"Invalid .pbix file format: {self.pbix_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to extract .pbix file: {e}")

    def read_model(self) -> Dict:
        """
        Read and parse the semantic model data.
        Uses PBIXRay for binary DataModel, falls back to JSON.

        Returns:
            Parsed model data as dict
        """
        if self._model_data:
            return self._model_data

        if not self.temp_dir:
            self.extract_to_temp()

        if self._use_pbixray:
            # Build model dict from PBIXRay data
            self._model_data = self._build_model_from_pbixray()
            return self._model_data

        # Fallback to JSON model.bim
        return self._read_model_json()

    def _build_model_from_pbixray(self) -> Dict:
        """Build model dict from PBIXRay data."""
        model = {
            "name": self.pbix_path.stem,
            "tables": self.get_tables(),
            "relationships": self.get_relationships(),
        }
        return {"model": model}

    def _read_model_json(self) -> Dict:
        """Read model from JSON file (legacy support)."""
        # Try different possible paths for model.bim
        possible_paths = [
            self.temp_dir / "DataModel" / "model.bim",
            self.temp_dir / "model.bim",
            self.temp_dir / "DataModelSchema",
        ]

        model_path = None
        for path in possible_paths:
            if path.exists():
                model_path = path
                break

        if not model_path:
            # Try to find any .bim file
            bim_files = list(self.temp_dir.rglob("*.bim"))
            if bim_files:
                model_path = bim_files[0]
            else:
                raise FileNotFoundError(
                    f"model.bim not found and PBIXRay not available for: {self.pbix_path}"
                )

        try:
            with open(model_path, 'r', encoding='utf-8') as f:
                self._model_data = json.load(f)
            logger.info(f"Successfully read model.bim from {model_path}")
            return self._model_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in model.bim: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to read model.bim: {e}")

    def get_tables(self) -> List[Dict]:
        """
        Extract table definitions from model.

        Returns:
            List of table definitions with columns
        """
        if self._tables_cache is not None:
            return self._tables_cache

        if not self.temp_dir:
            self.extract_to_temp()

        if self._use_pbixray:
            self._tables_cache = self._get_tables_pbixray()
            return self._tables_cache

        # Fallback to JSON
        return self._get_tables_json()

    def _get_tables_pbixray(self) -> List[Dict]:
        """Get tables from PBIXRay."""
        tables = []

        # Get schema for column info
        schema_df = self._pbixray.schema

        for table_name in self._pbixray.tables:
            # Get column info from schema
            table_schema = schema_df[schema_df['TableName'] == table_name]

            columns = []
            for _, row in table_schema.iterrows():
                col = {
                    "name": row['ColumnName'],
                    "dataType": self._map_pandas_type(row['PandasDataType']),
                    "isNullable": True,
                    "isKey": False,
                    "isUnique": False,
                }
                columns.append(col)

            # Get measures for this table
            measures = []
            if self._pbixray.dax_measures is not None and not self._pbixray.dax_measures.empty:
                table_measures = self._pbixray.dax_measures[
                    self._pbixray.dax_measures['TableName'] == table_name
                ]
                for _, row in table_measures.iterrows():
                    measure = {
                        "name": row['Name'],
                        "expression": row['Expression'] if row['Expression'] else "",
                        "displayFolder": row['DisplayFolder'] if row['DisplayFolder'] else "",
                        "description": row['Description'] if row['Description'] else "",
                    }
                    measures.append(measure)

            # Get hierarchies (from DAX columns)
            hierarchies = []

            table_def = {
                "name": table_name,
                "description": "",
                "columns": columns,
                "measures": measures,
                "hierarchies": hierarchies,
            }
            tables.append(table_def)

        return tables

    def _get_tables_json(self) -> List[Dict]:
        """Get tables from JSON model."""
        model = self.read_model()

        # Handle different Power BI schema versions
        if isinstance(model, dict):
            if "model" in model:
                model = model["model"]
            if "tables" in model:
                return model["tables"]
            if "model" in model and "tables" in model["model"]:
                return model["model"]["tables"]

        return []

    def get_relationships(self) -> List[Dict]:
        """
        Extract relationship definitions from model.

        Returns:
            List of relationship definitions
        """
        if self._relationships_cache is not None:
            return self._relationships_cache

        if not self.temp_dir:
            self.extract_to_temp()

        if self._use_pbixray:
            self._relationships_cache = self._get_relationships_pbixray()
            return self._relationships_cache

        # Fallback to JSON
        return self._get_relationships_json()

    def _get_relationships_pbixray(self) -> List[Dict]:
        """Get relationships from PBIXRay."""
        relationships = []

        if self._pbixray.relationships is None or self._pbixray.relationships.empty:
            return relationships

        for _, row in self._pbixray.relationships.iterrows():
            # Map cardinality
            cardinality_map = {
                "M:1": ("many", "one"),
                "1:M": ("one", "many"),
                "1:1": ("one", "one"),
                "M:M": ("many", "many"),
            }
            card = row.get('Cardinality', 'M:1')
            from_card, to_card = cardinality_map.get(card, ("many", "one"))

            # Map cross filter behavior
            cross_filter = row.get('CrossFilteringBehavior', 'Single')
            cross_filter_behavior = "bothDirections" if cross_filter == "Both" else "singleDirection"

            rel = {
                "fromTable": row['FromTableName'],
                "fromColumn": row['FromColumnName'],
                "toTable": row['ToTableName'] if row['ToTableName'] else "",
                "toColumn": row['ToColumnName'] if row['ToColumnName'] else "",
                "fromCardinality": from_card,
                "toCardinality": to_card,
                "crossFilteringBehavior": cross_filter_behavior,
                "isActive": bool(row.get('IsActive', True)),
                "name": f"{row['FromTableName']}_{row['ToTableName'] or 'Unknown'}",
            }
            relationships.append(rel)

        return relationships

    def _get_relationships_json(self) -> List[Dict]:
        """Get relationships from JSON model."""
        model = self.read_model()

        # Handle different Power BI schema versions
        if isinstance(model, dict):
            if "model" in model:
                model = model["model"]
            if "relationships" in model:
                return model["relationships"]
            if "model" in model and "relationships" in model["model"]:
                return model["model"]["relationships"]

        return []

    def get_measures(self) -> List[Dict]:
        """
        Extract DAX measures from all tables.

        Returns:
            List of measure definitions
        """
        if self._measures_cache is not None:
            return self._measures_cache

        if not self.temp_dir:
            self.extract_to_temp()

        if self._use_pbixray:
            self._measures_cache = self._get_measures_pbixray()
            return self._measures_cache

        # Fallback to JSON
        return self._get_measures_json()

    def _get_measures_pbixray(self) -> List[Dict]:
        """Get measures from PBIXRay."""
        measures = []

        if self._pbixray.dax_measures is None or self._pbixray.dax_measures.empty:
            return measures

        for _, row in self._pbixray.dax_measures.iterrows():
            measure = {
                "name": row['Name'],
                "expression": row['Expression'] if row['Expression'] else "",
                "displayFolder": row['DisplayFolder'] if row['DisplayFolder'] else "",
                "description": row['Description'] if row['Description'] else "",
                "table": row['TableName'],
            }
            measures.append(measure)

        return measures

    def _get_measures_json(self) -> List[Dict]:
        """Get measures from JSON model."""
        tables = self._get_tables_json()
        measures = []

        for table in tables:
            if "measures" in table:
                for measure in table["measures"]:
                    measure["table"] = table.get("name", "Unknown")
                    measures.append(measure)

        return measures

    def get_power_query(self) -> List[Dict]:
        """
        Extract Power Query (M) expressions.

        Returns:
            List of Power Query expressions per table
        """
        if not self._use_pbixray:
            return []

        if self._pbixray.power_query is None or self._pbixray.power_query.empty:
            return []

        queries = []
        for _, row in self._pbixray.power_query.iterrows():
            queries.append({
                "table": row['TableName'],
                "expression": row['Expression'],
            })

        return queries

    def get_dax_columns(self) -> List[Dict]:
        """
        Extract calculated columns (DAX expressions).

        Returns:
            List of DAX column definitions
        """
        if not self._use_pbixray:
            return []

        if self._pbixray.dax_columns is None or self._pbixray.dax_columns.empty:
            return []

        columns = []
        for _, row in self._pbixray.dax_columns.iterrows():
            columns.append({
                "table": row['TableName'],
                "name": row['ColumnName'],
                "expression": row['Expression'],
            })

        return columns

    def get_rls_rules(self) -> List[Dict]:
        """
        Extract Row-Level Security (RLS) rules.

        Returns:
            List of RLS rule definitions
        """
        if not self._use_pbixray:
            # Try JSON fallback
            return self._get_rls_json()

        if self._pbixray.rls is None or self._pbixray.rls.empty:
            return []

        rules = []
        for _, row in self._pbixray.rls.iterrows():
            rules.append({
                "role": row.get('RoleName', ''),
                "table": row.get('TableName', ''),
                "filter_expression": row.get('FilterExpression', ''),
            })

        return rules

    def _get_rls_json(self) -> List[Dict]:
        """Get RLS from JSON model."""
        model = self.read_model()
        rules = []

        if isinstance(model, dict):
            if "model" in model:
                model = model["model"]

            roles = model.get("roles", [])
            for role in roles:
                role_name = role.get("name", "")
                for perm in role.get("tablePermissions", []):
                    if perm.get("filterExpression"):
                        rules.append({
                            "role": role_name,
                            "table": perm.get("name", ""),
                            "filter_expression": perm.get("filterExpression", ""),
                        })

        return rules

    def get_table_data(self, table_name: str) -> Optional[Any]:
        """
        Get actual data from a table (PBIXRay only).

        Args:
            table_name: Name of the table

        Returns:
            DataFrame with table data or None
        """
        if not self._use_pbixray:
            logger.warning("Table data extraction requires PBIXRay")
            return None

        try:
            return self._pbixray.get_table(table_name)
        except Exception as e:
            logger.error(f"Failed to get table data for {table_name}: {e}")
            return None

    def _map_pandas_type(self, pandas_type: str) -> str:
        """Map pandas dtype to Power BI data type."""
        type_mapping = {
            "string": "string",
            "object": "string",
            "int64": "int64",
            "Int64": "int64",
            "float64": "double",
            "Float64": "double",
            "bool": "boolean",
            "datetime64[ns]": "datetime",
            "datetime64": "datetime",
        }
        return type_mapping.get(pandas_type, "string")

    def cleanup(self):
        """Remove temporary extraction directory."""
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
            finally:
                self.temp_dir = None

        # Clear PBIXRay reference
        self._pbixray = None

    @property
    def is_pbixray_available(self) -> bool:
        """Check if PBIXRay is being used."""
        return self._use_pbixray

    def read_report(self) -> Optional[Dict]:
        """
        Read and parse the report.json file (optional, for context).

        Returns:
            Parsed JSON report data or None if not found
        """
        if not self.temp_dir:
            self.extract_to_temp()

        report_path = self.temp_dir / "Report" / "report.json"
        if not report_path.exists():
            # Try Layout file (UTF-16)
            layout_path = self.temp_dir / "Report" / "Layout"
            if layout_path.exists():
                try:
                    with open(layout_path, 'rb') as f:
                        content = f.read()
                    text = content.decode('utf-16-le')
                    return json.loads(text)
                except Exception as e:
                    logger.warning(f"Failed to read Layout: {e}")

            logger.warning("report.json not found in .pbix file")
            return None

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read report.json: {e}")
            return None
