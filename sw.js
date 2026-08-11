const CACHE_NAME='diario-alimentare-v31';

const CORE_ASSETS=[
  './',
  './index.html',
  './manifest.webmanifest',
  './crea_foods.js',
  './swiss_foods.js',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE_NAME);
    await Promise.allSettled(
      CORE_ASSETS.map(url=>cache.add(new Request(url,{cache:'reload'})))
    );
    await self.skipWaiting();
  })());
});

self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();

    await Promise.all(
      keys
        .filter(k=>k.startsWith('diario-alimentare-') && k!==CACHE_NAME)
        .map(k=>caches.delete(k))
    );

    await self.clients.claim();
  })());
});

self.addEventListener('message',event=>{
  if(event.data && event.data.type==='SKIP_WAITING'){
    self.skipWaiting();
  }
});

async function networkFirstNavigation(request){
  try{
    const fresh=await fetch(request,{cache:'no-store'});

    if(fresh && fresh.ok){
      const cache=await caches.open(CACHE_NAME);
      cache.put('./index.html',fresh.clone()).catch(()=>{});
    }

    return fresh;
  }catch(e){
    return (
      await caches.match('./index.html')
    ) || (
      await caches.match('./')
    ) || Response.error();
  }
}

self.addEventListener('fetch',event=>{
  const request=event.request;

  if(request.method!=='GET') return;

  const url=new URL(request.url);

  if(url.origin!==self.location.origin) return;

  // Per l'app e index.html: prova sempre prima la versione online.
  if(
    request.mode==='navigate' ||
    url.pathname.endsWith('/index.html') ||
    url.pathname.endsWith('/diario-alimentare/')
  ){
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  // Per gli altri file: usa la cache quando disponibile.
  event.respondWith((async()=>{
    const cached=await caches.match(request);

    if(cached) return cached;

    try{
      const fresh=await fetch(request);

      if(fresh && fresh.ok){
        const cache=await caches.open(CACHE_NAME);
        cache.put(request,fresh.clone()).catch(()=>{});
      }

      return fresh;
    }catch(e){
      return cached || Response.error();
    }
  })());
});
