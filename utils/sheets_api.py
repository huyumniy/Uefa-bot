import requests
import json


class GoogleSheetClient:
    """
    A helper class to fetch and parse data from a Google Sheets document
    using the “gviz/tq” endpoint. Provides:

      • fetch_sheet_data(): 
          Dynamically read all headers in row 1, then fetch A2:⟨last_column⟩,
          returning a list of [match, {header→value, …}].

      • fetch_sheet_columns(sheet_range):
          Fetch any arbitrary range (e.g. 'A1:H100') and format the first two columns,
          converting dates/numbers/strings appropriately.
    """

    def __init__(self, sheet_url: str, sheet_title: str = "main"):
        """
        Initialize with the full sheet URL (e.g. "https://docs.google.com/spreadsheets/d/ABC123…/edit")
        and an optional sheet title (defaults to "main").
        """
        self.sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        self.sheet_title = sheet_title

    def fetch_sheet_data(self) -> list[list]:
        """
        High‐level method to read all of row 1, discover every non‐empty header,
        then fetch rows A2:⟨last_column⟩ and return a list of:
            [ match_value, { header_name: value_as_str_or_empty, … } ]

        Steps (in order):
          1) _get_column_headers() → returns ["Match", "Category 1", "Category 2", …]
          2) Compute last column letter from the number of headers
          3) _get_data_rows(last_column) → returns raw row‐objects
          4) For each row, call _parse_single_row(cells, headers)
             → skip rows whose “match” is blank
        """
        headers = self._get_column_headers()
        if not headers:
            return []

        last_col = self._column_index_to_letter(len(headers))

        raw_rows = self._get_data_rows(last_col)

        result: list[list] = []
        for row_obj in raw_rows:
            cells = row_obj.get("c", [])
            parsed = self._parse_single_row(cells, headers)
            if parsed is not None:
                match_value, categories_dict = parsed
                result.append([match_value, categories_dict])

        return result

    def fetch_sheet_columns(self, sheet_range: str) -> list[list] | None:
        """
        Fetches an arbitrary range (e.g. 'A1:H100') from the same sheet,
        then returns a list of rows where only columns 0 and 1 are formatted:

          • Dates → use cell['f'] if present, else str(cell['v'])
          • Numbers → convert floats with .is_integer() to int
          • Strings → strip()
          • Else → raw value

        Returns a list of [col0_value, col1_value] for each row, or None on error.
        """
        try:
            data = self._fetch_sheet_json(sheet_range)
            table = data.get("table", {})
            rows = table.get("rows", [])
            cols = table.get("cols", [])
            if not rows or not cols:
                return []

            formatted: list[list] = []
            for row in rows:
                cells = row.get("c", [])
                formatted_row: list[None | str | int] = []
                for idx in (0, 1):
                    # If cell is missing, out of bounds, or explicitly None → append None
                    if idx >= len(cells) or cells[idx] is None:
                        formatted_row.append(None)
                        continue

                    cell = cells[idx]
                    col_type = cols[idx].get("type")
                    raw_val = cell.get("v")

                    if raw_val is None:
                        formatted_row.append(None)
                    elif col_type == "date":
                        formatted_row.append(cell.get("f", str(raw_val)))
                    elif col_type == "number":
                        if isinstance(raw_val, float) and raw_val.is_integer():
                            formatted_row.append(int(raw_val))
                        else:
                            formatted_row.append(raw_val)
                    elif col_type == "string":
                        formatted_row.append(str(raw_val).strip())
                    else:
                        formatted_row.append(raw_val)

                formatted.append(formatted_row)
            return formatted

        except Exception as e:
            print(f"An error occurred in fetch_sheet_columns: {e}")
            return None


    def _get_column_headers(self) -> list[str]:
        """
        Read all of row 1 (range="1:1") and return a Python list of every non‐empty header string.
        Stops when the first truly blank cell is encountered.
        """
        data = self._fetch_sheet_json("1:1")
        rows = data.get("table", {}).get("rows", [])
        if not rows or not rows[0].get("c"):
            return []

        header_cells = rows[0]["c"]
        headers: list[str] = []
        for cell in header_cells:
            if cell is None or cell.get("v") in (None, ""):
                break
            headers.append(str(cell["v"]))
        return headers

    def _get_data_rows(self, last_column_letter: str) -> list[dict]:
        """
        Fetch all rows from A2 → ⟨last_column_letter⟩ and return the raw list of row‐objects.
        Each row‐object has a "c" key: a list of cell‐objects.
        """
        data_range = f"A2:{last_column_letter}"
        data = self._fetch_sheet_json(data_range)
        return data.get("table", {}).get("rows", [])

    def _parse_single_row(self, cells: list[dict], headers: list[str]) -> tuple[str, dict[str, str]] | None:
        """
        Convert a single row's list of cell‐objects into (match, categories_dict).
        - match = cells[0]["v"]  (if blank or None → return None to skip this row)
        - categories_dict = { headers[i]: str(int(raw)) or "" } for each i in 1…len(headers)-1
        """
        def get_val(idx: int):
            try:
                cell = cells[idx]
                return cell.get("v") if cell is not None else None
            except (IndexError, AttributeError):
                return None

        match_val = get_val(0)
        if match_val in (None, ""):
            return None

        categories: dict[str, str] = {}
        for idx in range(1, len(headers)):
            header_name = headers[idx]
            raw_val = get_val(idx)
            if raw_val not in (None, ""):
                parsed = self._parse_nullable_int(raw_val)
                categories[header_name] = str(parsed) if (parsed is not None) else ""
            else:
                categories[header_name] = ""
        return match_val, categories

    def _fetch_sheet_json(self, cell_range: str) -> dict:
        """
        Low‐level helper to call the “gviz/tq” endpoint for a given A1‐style cell_range,
        strip off the Google‐JSAPI wrapper, and return the parsed JSON dictionary.
        """
        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/gviz/tq" \
              f"?sheet={self.sheet_title}&range={cell_range}"
        resp = requests.get(url)
        resp.raise_for_status()
        text = resp.text
        raw_json = text[47:-2]
        return json.loads(raw_json)

    @staticmethod
    def _column_index_to_letter(index: int) -> str:
        """
        Convert a 1-based column index to Excel‐style letters:
          1 → "A", 2 → "B", …, 26 → "Z", 27 → "AA", etc.
        """
        letters = []
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters.append(chr(65 + remainder))
        return "".join(reversed(letters))

    @staticmethod
    def _parse_nullable_int(raw) -> int | None:
        """
        Attempt to convert raw to an integer. If raw is None or not parseable,
        return None.
        """
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    sheet_url = "https://docs.google.com/spreadsheets/d/1gIooGghzO341-tbhkw0eIALh08PsTuo00YGTa_1rIls/edit"
    client = GoogleSheetClient(sheet_url, "main")
    
    data = client.fetch_sheet_data()
    print(data)