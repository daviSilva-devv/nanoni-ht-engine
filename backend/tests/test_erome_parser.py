from nanoni.integrations.source.erome import EromeAdapter


def test_erome_album_becomes_ordered_manifest():
    html = """
    <html><head><meta property='og:title' content='Pack Test'></head><body>
      <div class='media-group'><div class='img' data-src='https://s1.erome.com/1.jpg'></div></div>
      <div class='media-group'><video><source src='https://v1.erome.com/2.mp4'></video></div>
      <div class='media-group'><div class='img' data-src='https://s1.erome.com/3.jpg'></div></div>
    </body></html>
    """
    manifest = EromeAdapter.parse_album_html("https://www.erome.com/abc123", html)
    assert manifest.title == "Pack Test"
    assert manifest.source_item_id == "abc123"
    assert [m.media_type for m in manifest.media] == ["IMAGE", "VIDEO", "IMAGE"]
    assert [m.metadata["position"] for m in manifest.media] == [0, 1, 2]
