function visibleMessage() {
  const selectors = [
    "[data-message-id]",
    "[data-mid]",
    '[class*="message-list-item"]',
    '[class*="Message"]',
  ];
  const candidates = [...document.querySelectorAll(selectors.join(","))].filter((element) => {
    const rect = element.getBoundingClientRect();
    return rect.width > 100 && rect.height > 20 && rect.bottom > 0 && rect.top < innerHeight;
  });
  const hovered = candidates.find((element) => element.matches(":hover"));
  if (hovered) return hovered;
  const center = innerHeight / 2;
  return candidates.sort((left, right) => {
    const leftRect = left.getBoundingClientRect();
    const rightRect = right.getBoundingClientRect();
    return (
      Math.abs((leftRect.top + leftRect.bottom) / 2 - center) -
      Math.abs((rightRect.top + rightRect.bottom) / 2 - center)
    );
  })[0];
}

function messageId(element) {
  const direct = element.dataset.messageId || element.dataset.mid || element.id;
  if (direct) return direct;
  const link = element.querySelector('a[href*="/"],a[href*="#"]');
  return link?.href || `${location.pathname}${location.hash}`;
}

function visiblePostContext() {
  const selected = visibleMessage();
  if (!selected) throw new Error("Nenhuma mensagem visível foi encontrada.");
  const postId = messageId(selected);
  const media = [];
  const seen = new Set();

  for (const [index, video] of [...selected.querySelectorAll("video")].entries()) {
    const locator = video.currentSrc || video.src || `telegram-web-video-${index}`;
    if (seen.has(locator)) continue;
    seen.add(locator);
    media.push({
      external_item_id: `${postId}:video:${index}`,
      media_type: "VIDEO",
      source_reference: locator,
      duration_seconds: Number.isFinite(video.duration) ? video.duration : null,
      width: video.videoWidth || null,
      height: video.videoHeight || null,
      downloadable: false,
      metadata: { browser_detected: true },
    });
  }
  for (const [index, image] of [...selected.querySelectorAll("img")].entries()) {
    const rect = image.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 120) continue;
    const locator = image.currentSrc || image.src || `telegram-web-image-${index}`;
    if (seen.has(locator)) continue;
    seen.add(locator);
    media.push({
      external_item_id: `${postId}:image:${index}`,
      media_type: "IMAGE",
      source_reference: locator,
      width: image.naturalWidth || null,
      height: image.naturalHeight || null,
      downloadable: false,
      metadata: { browser_detected: true },
    });
  }

  const chatTitle =
    document.querySelector("header h3, header [dir='auto'], [class*='chat-info'] [dir='auto']")
      ?.textContent || document.title;
  return {
    source: "telegram-helper",
    source_item_id: `${location.pathname}:${postId}`,
    source_url: location.href,
    title: chatTitle.trim(),
    caption: (selected.innerText || "").trim().slice(0, 4000),
    media,
    metadata: {
      captured_at: new Date().toISOString(),
      assisted_import: true,
      telegram_post_id: postId,
      detected_media_count: media.length,
    },
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "NANONI_CONTEXT") return false;
  try {
    sendResponse({ ok: true, manifest: visiblePostContext() });
  } catch (error) {
    sendResponse({ ok: false, error: String(error) });
  }
  return true;
});
