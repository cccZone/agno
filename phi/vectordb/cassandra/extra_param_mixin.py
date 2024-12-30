from cassio.table.mixins.base_table import BaseTableMixin
from cassio.table.table_types import ColumnSpecType
from typing import List


class ExtraParamMixin(BaseTableMixin):
    def _schema_da(self) -> List[ColumnSpecType]:
        return super()._schema_da() + [
            ("document_name", "TEXT"),
        ]
