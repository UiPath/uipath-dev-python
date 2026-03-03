export interface StateDbTable {
  name: string;
  row_count: number;
}

export interface StateDbColumn {
  name: string;
  type: string;
}

export interface StateDbTableData {
  columns: StateDbColumn[];
  rows: unknown[][];
  total: number;
}

export interface StateDbQueryResult {
  columns: StateDbColumn[];
  rows: unknown[][];
  row_count: number;
}
