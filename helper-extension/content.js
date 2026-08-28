function visiblePostContext(){
  const url=location.href;
  const selected=document.querySelector('[class*="message"]:hover') || document.activeElement?.closest?.('[class*="message"]');
  const text=(selected?.innerText || document.body.innerText || "").slice(0,2000);
  const videos=[...document.querySelectorAll('video')].filter(v=>{const r=v.getBoundingClientRect();return r.width>0&&r.height>0}).slice(-10).map((v,i)=>({media_type:"VIDEO",source_locator:v.currentSrc||v.src||`telegram-web-video-${i}`,duration_seconds:Number.isFinite(v.duration)?v.duration:null,width:v.videoWidth||null,height:v.videoHeight||null,downloadable:false,metadata:{browser_detected:true}}));
  const images=[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.width>120&&r.height>120}).slice(-10).map((img,i)=>({media_type:"IMAGE",source_locator:img.currentSrc||img.src||`telegram-web-image-${i}`,width:img.naturalWidth||null,height:img.naturalHeight||null,downloadable:false,metadata:{browser_detected:true}}));
  const itemId=location.hash || url;
  return {source:"telegram-helper",source_item_id:itemId,source_url:url,title:document.title,caption:text,media:[...images,...videos],metadata:{captured_at:new Date().toISOString(),assisted_import:true}};
}
chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{if(msg?.type==="NANONI_CONTEXT"){sendResponse(visiblePostContext());return true;}});
