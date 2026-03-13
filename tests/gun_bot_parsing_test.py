import unittest

from gun_bot import (
    ListingDetails,
    SearchListing,
    format_telegram_message,
    listing_is_closed,
    listing_matches_keywords,
    parse_listing_details,
    parse_search_results,
)


SEARCH_HTML = """
<div id="dj-classifieds">
  <div class="dj-items">
    <div class="item_row item_row0 item_new">
      <div class="item_title">
        <h3><a href="/classifieds/firearms/ad/glock-19-gen-6-159507">Glock 19 gen 6</a></h3>
      </div>
      <div class="item_cat_region_outer">
        <div class="item_region"><a href="/phoenix">Phoenix</a></div>
      </div>
      <div class="item_desc">
        <a href="/classifieds/firearms/ad/glock-19-gen-6-159507">Brand new</a>
      </div>
      <div class="item_details">
        <div class="item_price"><span class="price_val">750.00</span> <span class="price_unit">USD</span></div>
        <div class="item_date_start" title="Added">6 minutes ago</div>
      </div>
    </div>
  </div>
</div>
"""


DETAIL_HTML = """
<div class="dj-item item_new">
  <div class="title_top info"><h2 itemprop="name">Sig P365</h2></div>
  <div class="dj-item-in">
    <div class="general_det">
      <div class="general_det_in">
        <div class="price_wrap row_gd">
          <div class="price">
            <span class="row_value"><span class="price_val">500.00</span> <span class="price_unit">USD</span></span>
          </div>
        </div>
        <div class="row_gd djcf_contact">
          <div class="contact_mainrow">
            <span class="row_value">6025551212</span>
          </div>
        </div>
        <div class="row_gd added">
          <span class="row_value">03-06-2026 14:03:08</span>
        </div>
      </div>
    </div>
    <div class="localization_det">
      <div class="row address"><span class="row_value">Glendale</span></div>
    </div>
    <div class="description">
      <div class="desc_content"><p>Sig P365 in excellent condition. It is MOS.</p></div>
    </div>
  </div>
</div>
"""


class GunBotParsingTest(unittest.TestCase):
    def test_parse_search_results_extracts_expected_fields(self) -> None:
        results = parse_search_results(SEARCH_HTML)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ad_id, "159507")
        self.assertEqual(results[0].title, "Glock 19 gen 6")
        self.assertEqual(results[0].location, "Phoenix")
        self.assertEqual(results[0].price, "750.00 USD")
        self.assertEqual(results[0].relative_time, "6 minutes ago")

    def test_listing_keyword_match_handles_spacing_and_case(self) -> None:
        listing = SearchListing(
            ad_id="159507",
            title="Glock19 Gen 6",
            url="https://gunsarizona.com/classifieds/firearms/ad/glock-19-gen-6-159507",
            snippet="Brand new",
        )

        self.assertTrue(listing_matches_keywords(listing, ["Glock 19"]))
        self.assertTrue(listing_matches_keywords(listing, ["glock19"]))
        self.assertFalse(listing_matches_keywords(listing, ["Daniel Defense"]))

    def test_listing_is_closed_detects_sold_and_pending_markers(self) -> None:
        sold_listing = SearchListing(
            ad_id="1",
            title="**SOLD** Glock 19x Near Mint",
            url="https://gunsarizona.com/classifieds/firearms/ad/1",
            snippet="No longer available.",
        )
        pending_listing = SearchListing(
            ad_id="2",
            title="[PENDING] Sig P365",
            url="https://gunsarizona.com/classifieds/firearms/ad/2",
            snippet="Pending pickup",
        )
        active_listing = SearchListing(
            ad_id="3",
            title="Sig P365 XMacro",
            url="https://gunsarizona.com/classifieds/firearms/ad/3",
            snippet="Excellent condition",
        )

        self.assertTrue(listing_is_closed(sold_listing))
        self.assertTrue(listing_is_closed(pending_listing))
        self.assertFalse(listing_is_closed(active_listing))

    def test_parse_listing_details_prefers_primary_ad_fields(self) -> None:
        listing = SearchListing(
            ad_id="159497",
            title="Sig P365",
            url="https://gunsarizona.com/classifieds/firearms/ad/sig-p365-159497",
            price="N/A",
            location="Unknown",
            relative_time="Unknown",
            snippet="",
        )

        details = parse_listing_details(DETAIL_HTML, listing)

        self.assertEqual(
            details,
            ListingDetails(
                title="Sig P365",
                price="500.00 USD",
                location="Glendale",
                added="03-06-2026 14:03:08",
                description="Sig P365 in excellent condition. It is MOS.",
                contact="6025551212",
            ),
        )

    def test_format_telegram_message_escapes_html(self) -> None:
        listing = SearchListing(
            ad_id="1",
            title="Sig <P365>",
            url="https://example.com/ad/1",
        )
        details = ListingDetails(
            title="Sig <P365>",
            price="500.00 USD",
            location="Glendale & Peoria",
            added="today",
            description="Use <html> safely",
            contact="6025551212",
        )

        message = format_telegram_message(listing, details)

        self.assertIn("<b>GunsArizona Listing Match</b>", message)
        self.assertIn("Sig &lt;P365&gt;", message)
        self.assertIn("Price: $500.00", message)
        self.assertIn("Glendale &amp; Peoria", message)
        self.assertIn("Use &lt;html&gt; safely", message)
        self.assertIn("View listing on GunsArizona", message)
        self.assertIn('href="https://example.com/ad/1"', message)


if __name__ == "__main__":
    unittest.main()
