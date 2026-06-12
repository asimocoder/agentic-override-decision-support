import unittest
import pandas as pd
from data_ingestor import DataIngestor


class TestBuildEntityMapping(unittest.TestCase):
    """Test entity mapping extraction from structured columns."""

    def setUp(self):
        self.ingestor = DataIngestor()

    def test_column_header_scan_director_names(self):
        """Extract names from columns with director patterns."""
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma"],
                "Director 2": ["Priya Singh"],
                "Industry": ["Manufacturing"]
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Rajesh Sharma", mapping)
        self.assertIn("Priya Singh", mapping)
        self.assertEqual(mapping["Rajesh Sharma"], "PERSON_1")
        self.assertEqual(mapping["Priya Singh"], "PERSON_2")

    def test_column_header_scan_related_companies(self):
        """Extract names from columns with related company patterns."""
        sheets = {
            "scoring": pd.DataFrame({
                "Related Company": ["ABC Industries Ltd"],
                "Group Company": ["XYZ Holdings"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("ABC Industries Ltd", mapping)
        self.assertIn("XYZ Holdings", mapping)
        self.assertEqual(mapping["ABC Industries Ltd"], "ENTITY_1")
        self.assertEqual(mapping["XYZ Holdings"], "ENTITY_2")

    def test_key_value_row_scan(self):
        """Extract names from key-value rows (parameter in col 0, value in col 1)."""
        sheets = {
            "scoring": pd.DataFrame({
                0: ["Director 1", "Related Company", "Other"],
                1: ["Rajesh Sharma", "ABC Industries Ltd", "value"]
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Rajesh Sharma", mapping)
        self.assertIn("ABC Industries Ltd", mapping)

    def test_skip_nan_empty_values(self):
        """Skip NaN, None, and empty string values."""
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma", None, "", "Priya Singh"],
                "Director 2": ["", None, "xyz", "abc"]
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        # Only non-empty, non-None values should be in mapping
        self.assertIn("Rajesh Sharma", mapping)
        self.assertIn("Priya Singh", mapping)
        self.assertIn("xyz", mapping)
        self.assertIn("abc", mapping)
        # Empty strings and None should not be in mapping
        self.assertEqual(len([v for v in mapping.keys() if not v or v in ("", None)]), 0)

    def test_deduplication_across_lists(self):
        """Ensure same name in both director and company lists is mapped once."""
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma"],
                "Related Company": ["Rajesh Sharma"]  # Same name appears as company
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        # Should appear only once in mapping
        self.assertEqual(len([k for k in mapping.keys() if k == "Rajesh Sharma"]), 1)
        # Should be assigned to PERSON (first scanned)
        self.assertEqual(mapping["Rajesh Sharma"], "PERSON_1")

    def test_empty_sheets(self):
        """Return empty mapping for sheets with no entity names."""
        sheets = {
            "financials": pd.DataFrame({
                "Revenue": [1000000],
                "Expense": [500000]
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertEqual(mapping, {})

    def test_multiple_sheets(self):
        """Extract entities from multiple sheets correctly."""
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma"]
            }),
            "debtor_creditor": pd.DataFrame({
                "Related Party": ["ABC Industries"]
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Rajesh Sharma", mapping)
        self.assertIn("ABC Industries", mapping)

    def test_position_column_scan_director(self):
        """Extract names from Name+Position column structure where Position=Director."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name": ["Akshay Makhija", "Ajay Makhija", "Name"],
                "Position": ["Director", "Director", "Position"],
                "Age (yrs)": [34, 59, None],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Akshay Makhija", mapping)
        self.assertIn("Ajay Makhija", mapping)

    def test_position_column_scan_partner(self):
        """Extract names from Name+Position column structure where Position=Partner."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name": ["Suresh Patel"],
                "Position": ["Partner"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Suresh Patel", mapping)

    def test_position_column_scan_skips_header_row(self):
        """Position-column scan skips rows where Name value is 'Name' (header row)."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name": ["Name", "Akshay Makhija"],
                "Position": ["Position", "Director"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertNotIn("Name", mapping)
        self.assertIn("Akshay Makhija", mapping)

    def test_shareholder_column_extracted(self):
        """Extract names from Shareholder and Share Holder column variants."""
        sheets = {
            "scoring": pd.DataFrame({
                "Shareholder": ["Akshay Makhija"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Akshay Makhija", mapping)

    def test_share_holder_column_extracted(self):
        """Extract names from 'Share Holder' (with space) column."""
        sheets = {
            "scoring": pd.DataFrame({
                "Share Holder": ["Priya Singh"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Priya Singh", mapping)

    def test_name_of_the_company_column_extracted(self):
        """Extract entity from 'Name of the Company' column (group company table)."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name of the Company": ["Ramashray Finefoods LLP", "Nutrabella Foods LLP"],
                "DOI": ["5-11-20", "3-5-18"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Ramashray Finefoods LLP", mapping)
        self.assertIn("Nutrabella Foods LLP", mapping)
        self.assertEqual(mapping["Ramashray Finefoods LLP"], "ENTITY_1")

    def test_name_of_company_column_extracted(self):
        """Extract entity from 'Name of Company' column (without 'the')."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name of Company": ["ABC Holdings LLP"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("ABC Holdings LLP", mapping)

    def test_designation_column_scan(self):
        """Position-column scan fires when column is named 'Designation' not 'Position'."""
        sheets = {
            "scoring": pd.DataFrame({
                "Name": ["Meena Aarav Joshi", "Suresh Patel"],
                "Designation": ["Director", "Partner"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Meena Aarav Joshi", mapping)
        self.assertIn("Suresh Patel", mapping)

    def test_option_c_dedup_known_person_added(self):
        """
        Option C: bare Name column (no Position/Designation) — a name already known
        from a structured column in another sheet is added when it re-appears here.
        Covers director names repeated in Consumer CIBIL bureau sections.
        """
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma"],
            }),
            "bureau": pd.DataFrame({
                # Name column only — no Position or Designation column
                "Name": ["Rajesh Sharma"],
                "Account": ["HDFC CC"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        # Known person still in mapping (dedup means only one entry)
        self.assertIn("Rajesh Sharma", mapping)
        self.assertEqual(mapping["Rajesh Sharma"], "PERSON_1")

    def test_option_c_dedup_unknown_name_excluded(self):
        """
        Option C: bare Name column — a name that does NOT appear in any structured
        column is NOT added. Prevents bank, lender, and counterparty names from
        polluting the entity mapping.
        """
        sheets = {
            "scoring": pd.DataFrame({
                "Director 1": ["Rajesh Sharma"],
            }),
            "bureau": pd.DataFrame({
                # HDFC Bank is a lender name — unknown to entity mapping
                "Name": ["HDFC Bank Ltd"],
                "Account": ["CC"],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertNotIn("HDFC Bank Ltd", mapping)

    def test_mid_sheet_header_scan_designation(self):
        """
        Mid-sheet header scan: Name and Designation appear as a data row (not as
        DataFrame column headers) — simulates a directors sub-table embedded mid-sheet
        as seen in real CAMs where pd.read_excel() treats row 1 as headers and all
        subsequent section headers become data rows.

        The sheet has 'TAT Sheet' as the actual column header (row 1), with the
        directors sub-table header ('Name', 'Designation') appearing at row 24.
        build_entity_mapping() must detect the sub-table header and extract director
        names from the rows below it.
        """
        # Simulate the DataFrame as pd.read_excel() would produce it:
        # Column headers are row 1 of the real sheet (Unnamed cols).
        # The directors sub-table header appears as a data row.
        sheets = {
            "Borrower": pd.DataFrame({
                "TAT Sheet": [
                    "Details of Proprietor/ Partners/ Directors",  # section label row
                    "Name",                                         # sub-table header row
                    "LAKSHMIKUMARI YELAMANCHI",                    # data row 1
                    "YELLAMANCHI VENKATA NAGA MOHAN",              # data row 2
                    None,                                           # empty row — end of sub-table
                ],
                "Unnamed: 1": [
                    None,
                    "Age",
                    61,
                    64,
                    None,
                ],
                "Unnamed: 2": [
                    None,
                    "Designation",
                    "Director",
                    "Managing Director",
                    None,
                ],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("LAKSHMIKUMARI YELAMANCHI", mapping)
        self.assertIn("YELLAMANCHI VENKATA NAGA MOHAN", mapping)

    def test_mid_sheet_header_scan_non_director_rows_excluded(self):
        """
        Mid-sheet header scan: rows below the sub-table header where the role column
        does not match a known PERSON_POSITION_VALUE are not added.
        """
        sheets = {
            "Borrower": pd.DataFrame({
                "TAT Sheet": [
                    "Name",
                    "Rajesh Sharma",
                    "HDFC Bank Ltd",   # lender row — role is not a known position value
                ],
                "Unnamed: 1": [
                    "Designation",
                    "Director",
                    "Lender",          # not in PERSON_POSITION_VALUES
                ],
            })
        }
        mapping = self.ingestor.build_entity_mapping(sheets)
        self.assertIn("Rajesh Sharma", mapping)
        self.assertNotIn("HDFC Bank Ltd", mapping)


class TestSubstituteValue(unittest.TestCase):
    """Test single-cell value substitution."""

    def setUp(self):
        self.ingestor = DataIngestor()

    def test_substitute_matching_string(self):
        """Replace exact string match in cell value."""
        mapping = {"Rajesh Sharma": "PERSON_1"}
        result = self.ingestor._substitute_value("Rajesh Sharma", mapping)
        self.assertEqual(result, "PERSON_1")

    def test_substitute_substring_match(self):
        """Replace partial matches within a string."""
        mapping = {"Rajesh Sharma": "PERSON_1"}
        result = self.ingestor._substitute_value(
            "Director: Rajesh Sharma (Promoter)", mapping
        )
        self.assertEqual(result, "Director: PERSON_1 (Promoter)")

    def test_non_string_passthrough(self):
        """Non-string values pass through unchanged."""
        mapping = {"Rajesh Sharma": "PERSON_1"}
        self.assertEqual(self.ingestor._substitute_value(123, mapping), 123)
        self.assertEqual(self.ingestor._substitute_value(45.67, mapping), 45.67)
        self.assertEqual(self.ingestor._substitute_value(None, mapping), None)

    def test_empty_mapping(self):
        """Empty mapping returns value unchanged."""
        mapping = {}
        result = self.ingestor._substitute_value("Rajesh Sharma", mapping)
        self.assertEqual(result, "Rajesh Sharma")

    def test_multiple_substitutions_in_one_value(self):
        """Multiple entity names in one cell all get substituted."""
        mapping = {
            "Rajesh Sharma": "PERSON_1",
            "ABC Industries": "ENTITY_1"
        }
        result = self.ingestor._substitute_value(
            "Rajesh Sharma is director of ABC Industries",
            mapping
        )
        self.assertEqual(result, "PERSON_1 is director of ENTITY_1")


class TestSubstituteDataframe(unittest.TestCase):
    """Test DataFrame-wide substitution."""

    def setUp(self):
        self.ingestor = DataIngestor()

    def test_substitute_all_string_columns(self):
        """Substitution applied to all string values across DataFrame."""
        df = pd.DataFrame({
            "Director": ["Rajesh Sharma", "Priya Singh"],
            "Company": ["ABC Industries", "XYZ Corp"],
            "Amount": [100000, 200000]
        })
        mapping = {
            "Rajesh Sharma": "PERSON_1",
            "Priya Singh": "PERSON_2",
            "ABC Industries": "ENTITY_1",
            "XYZ Corp": "ENTITY_2"
        }
        result = self.ingestor._substitute_dataframe(df, mapping)
        self.assertEqual(result["Director"].iloc[0], "PERSON_1")
        self.assertEqual(result["Director"].iloc[1], "PERSON_2")
        self.assertEqual(result["Company"].iloc[0], "ENTITY_1")
        self.assertEqual(result["Company"].iloc[1], "ENTITY_2")
        # Numeric column unchanged
        self.assertEqual(result["Amount"].iloc[0], 100000)

    def test_preserve_dataframe_structure(self):
        """DataFrame shape and column names preserved."""
        df = pd.DataFrame({
            "Director": ["Rajesh Sharma"],
            "Company": ["ABC Industries"]
        })
        mapping = {
            "Rajesh Sharma": "PERSON_1",
            "ABC Industries": "ENTITY_1"
        }
        result = self.ingestor._substitute_dataframe(df, mapping)
        self.assertEqual(result.shape, df.shape)
        self.assertEqual(list(result.columns), list(df.columns))

    def test_empty_mapping_returns_copy(self):
        """Empty mapping returns DataFrame copy with no changes."""
        df = pd.DataFrame({
            "Director": ["Rajesh Sharma"],
            "Amount": [100000]
        })
        result = self.ingestor._substitute_dataframe(df, {})
        pd.testing.assert_frame_equal(result, df)


class TestEntityRestorer(unittest.TestCase):
    """Test reversal of placeholder mapping (PERSON_1 → real name)."""

    def test_restore_director_names(self):
        """Restore real director names from placeholders."""
        entity_mapping = {
            "Rajesh Sharma": "PERSON_1",
            "Priya Singh": "PERSON_2"
        }
        reverse_mapping = {
            "PERSON_1": "Rajesh Sharma",
            "PERSON_2": "Priya Singh"
        }
        director_names = ["PERSON_1", "PERSON_2"]
        restored = [reverse_mapping.get(name, name) for name in director_names]
        self.assertEqual(restored, ["Rajesh Sharma", "Priya Singh"])

    def test_restore_related_companies(self):
        """Restore real related company names from placeholders."""
        entity_mapping = {
            "ABC Industries Ltd": "ENTITY_1",
            "XYZ Holdings": "ENTITY_2"
        }
        reverse_mapping = {
            "ENTITY_1": "ABC Industries Ltd",
            "ENTITY_2": "XYZ Holdings"
        }
        related_companies = ["ENTITY_1", "ENTITY_2"]
        restored = [reverse_mapping.get(name, name) for name in related_companies]
        self.assertEqual(restored, ["ABC Industries Ltd", "XYZ Holdings"])

    def test_passthrough_if_not_in_mapping(self):
        """Names not in mapping pass through unchanged."""
        reverse_mapping = {
            "PERSON_1": "Rajesh Sharma"
        }
        names = ["PERSON_1", "UNKNOWN_NAME"]
        restored = [reverse_mapping.get(name, name) for name in names]
        self.assertEqual(restored, ["Rajesh Sharma", "UNKNOWN_NAME"])

    def test_empty_lists(self):
        """Empty lists remain empty after restoration."""
        reverse_mapping = {}
        restored = [reverse_mapping.get(name, name) for name in []]
        self.assertEqual(restored, [])


if __name__ == "__main__":
    unittest.main()
