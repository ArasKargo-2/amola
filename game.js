window.onload = function() {
  // --- Görseller ve oyun değişkenleri ---
  const images = {
    org1: new Image(), org2: new Image(), org3: new Image(),
    flip1: null, flip2: null, flip3: null,
    food: new Image(), finish: new Image(), brick: new Image(),
    spike: new Image(), cloud: new Image(), grass: new Image()
  };
  images.org1.src = "kedi1.png";
  images.org2.src = "kedi2.png";
  images.org3.src = "kedi3.png";
  images.food.src = "mama.png";
  images.finish.src = "bitis.png";
  images.brick.src = "tugla.png";
  images.spike.src = "diken.png";
  images.cloud.src = "bulut.png";
  images.grass.src = "cimen.png";
  function flipImage(img) {
    let c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    let ctx = c.getContext('2d');
    ctx.translate(img.width, 0); ctx.scale(-1, 1); ctx.drawImage(img, 0, 0);
    let flipped = new Image(); flipped.src = c.toDataURL(); return flipped;
  }
  const imageList = [images.org1, images.org2, images.org3, images.food, images.finish, images.brick, images.spike, images.cloud, images.grass];
  let loadedCount = 0;
  function checkLoaded() {
    if(loadedCount === imageList.length) {
      images.flip1 = flipImage(images.org1); images.flip2 = flipImage(images.org2); images.flip3 = flipImage(images.org3);
      setTimeout(() => { gameLoop(0); }, 100);
    }
  }
  imageList.forEach(img => { img.onload = () => { loadedCount++; checkLoaded(); }; });

  let canvas = document.getElementById("canvas");
  let ctx = canvas.getContext("2d");
  let screenW = 0, screenH = 0;
  function resize() { screenW = window.innerWidth; screenH = window.innerHeight; canvas.width = screenW; canvas.height = screenH; }
  window.addEventListener("resize", resize); resize();

  const LEVEL_HEIGHT = 3500;
  let level = { platforms: [], spikes: [], foods: [], finish: {x:300, y:200} };
  function generateLevel() {
    level.platforms = []; level.spikes = []; level.foods = [];
    level.platforms.push({x:0, y:LEVEL_HEIGHT-60, w:1600, h:60, type:'grass'});
    let y = LEVEL_HEIGHT-160, x = 100, dir = 1;
    for(let i=0;i<22;i++) {
      let w=220+Math.random()*60, h=36;
      level.platforms.push({x:x, y:y, w:w, h:h, type:'brick'});
      if(i%4===1) level.foods.push({x:x+Math.random()*(w-34), y:y-38});
      if(i%3===0 && i>0 && i<21) { let ex = x+Math.random()*(w-40); level.spikes.push({x:ex, y:y-16}); }
      x += dir*(240+Math.random()*100);
      if(x>screenW-280) { x=screenW-300; dir=-1; } if(x<60) { x=60; dir=1; }
      y -= 140+Math.random()*70;
    }
    level.finish = {x: x+70, y: y-60};
  }
  generateLevel();

  let player = { x:130, y:LEVEL_HEIGHT-130, w:66, h:66, dx:0, dy:0, onGround:false, dir:'left',
    health:100, food:0, canEat:false, isJumping:false, fallStartY:0, jumpCount:0, maxExtraJumps:2 };
  let keys = {w:false, a:false, d:false, s:false, space:false, up:false};
  let camY = 0, gameOver = false, gameWin = false;
  let walkFrame = 0, lastWalkFrameTime = 0;

  document.addEventListener("keydown", e=>{
    if(e.key==='w') keys.w=true; if(e.key==='a') keys.a=true; if(e.key==='d') keys.d=true;
    if(e.key==='s') keys.s=true; if(e.key===' '||e.code==="Space") keys.space=true; if(e.key==='ArrowUp') keys.up=true;
  });
  document.addEventListener("keyup", e=>{
    if(e.key==='w') keys.w=false; if(e.key==='a') keys.a=false; if(e.key==='d') keys.d=false;
    if(e.key==='s') keys.s=false; if(e.key===' '||e.code==="Space") keys.space=false; if(e.key==='ArrowUp') keys.up=false;
  });

  let lastTime = 0;
  function gameLoop(ts) {
    if(!lastTime) lastTime = ts; let dt = (ts - lastTime) / 1000; lastTime = ts;
    update(dt, ts); draw(ts); if(!gameOver && !gameWin) requestAnimationFrame(gameLoop);
  }

  function update(dt, ts) {
    if(gameOver || gameWin) return;
    if(keys.a && !keys.d) { player.dx = -4; player.dir='left'; }
    else if(keys.d && !keys.a) { player.dx = 4; player.dir='right'; }
    else player.dx = 0;
    if((keys.w||keys.up) && player.onGround) {
      player.dy = -11.5; player.onGround = false; player.isJumping = true; player.fallStartY = player.y; player.jumpCount=0;
    }
    if(keys.space && !player.onGround && player.jumpCount < player.maxExtraJumps) {
      if(!player.lastSpace) { player.dy = -11.5; player.jumpCount++; player.health -= 10; if(player.health<0) player.health=0; }
    }
    player.lastSpace = keys.space;
    player.dy += 0.5; if(player.dy > 14) player.dy = 14;
    player.x += player.dx; if(player.x < 0) player.x = 0; if(player.x + player.w > 1600) player.x = 1600 - player.w;
    let wasOnGround = player.onGround; player.onGround = false;
    for(let plat of level.platforms) {
      if(collide(player, plat)) {
        if(player.dy > 0 && player.y < plat.y) {
          player.y = plat.y - player.h; player.dy = 0; player.onGround = true;
          if(player.isJumping) {
            let fall = player.fallStartY - player.y;
            if(fall > 420) { let damage = Math.floor((fall-420)/7); player.health -= damage; if(player.health<0) player.health=0; }
            player.isJumping = false;
          } player.jumpCount = 0;
        } else if(player.dy < 0 && player.y > plat.y) { player.y = plat.y + plat.h; player.dy = 1; }
      }
    }
    player.y += player.dy; if(player.y > LEVEL_HEIGHT-player.h) { player.y = LEVEL_HEIGHT-player.h; player.dy = 0; player.onGround = true; player.jumpCount = 0; }
    for(let i=level.spikes.length-1; i>=0; i--) {
      let spk = level.spikes[i];
      if(rectCollide(player.x,player.y,player.w,player.h, spk.x,spk.y,28,18)) {
        player.health -= 20; if(player.health<0) player.health=0; level.spikes.splice(i,1);
      }
    }
    player.canEat = false;
    for(let i=0; i<level.foods.length; i++) {
      let f = level.foods[i];
      if(rectCollide(player.x,player.y,player.w,player.h, f.x, f.y, 32,32)) {
        player.canEat = true; if(keys.s) { player.food++; player.health += 32; if(player.health>100) player.health=100; level.foods.splice(i,1); }
      }
    }
    let fin = level.finish;
    if(rectCollide(player.x,player.y,player.w,player.h, fin.x, fin.y, 44,44)) { gameWin = true; setTimeout(()=>alert("Tebrikler! Oyunu bitirdin! Sayfayı yenile, yeniden oyna."), 120);}
    if(player.health<=0) { gameOver = true; setTimeout(()=>alert("Oyun Bitti! Yeniden başlamak için sayfayı yenileyin."), 120);}
    camY = Math.max(0, Math.min(player.y-screenH/2+80, LEVEL_HEIGHT-screenH));
    updateUI();

    // --- Animasyon sadece A veya D tuşuna BASILIYKEN çalışır ---
    if ((keys.a || keys.d) && player.onGround) {
      if (ts - lastWalkFrameTime > 220) { // 0.22 sn aralık
        walkFrame = 1 - walkFrame;
        lastWalkFrameTime = ts;
      }
    } else {
      walkFrame = 0;
      lastWalkFrameTime = ts;
    }
  }

  function draw(ts) {
    ctx.fillStyle = "#87ceeb"; ctx.fillRect(0,0,screenW,screenH);
    for(let i=0;i<10;i++) { let bx=(i*280)%1600+60, by=120+i*185-((camY)%185); ctx.globalAlpha=0.7;
      if(images.cloud.complete && images.cloud.naturalWidth > 0) ctx.drawImage(images.cloud, bx, by-240, 110, 68);
      else { ctx.beginPath(); ctx.arc(bx, by-240, 40, 0, Math.PI*2); ctx.fillStyle="#fff"; ctx.fill(); }
      ctx.globalAlpha=1.0;
    }
    for(let plat of level.platforms) {
      if(plat.type==='grass' && images.grass.complete && images.grass.naturalWidth > 0) ctx.drawImage(images.grass, plat.x, plat.y-camY, plat.w, plat.h);
      else if(plat.type==='brick' && images.brick.complete && images.brick.naturalWidth > 0) for(let px=0;px<plat.w;px+=36) ctx.drawImage(images.brick, plat.x+px, plat.y-camY, 36, plat.h);
      else { ctx.fillStyle=plat.type==='grass'?"#3c9e2f":"#b5651d"; ctx.fillRect(plat.x, plat.y-camY, plat.w, plat.h);}
    }
    for(let spk of level.spikes) {
      if(images.spike.complete && images.spike.naturalWidth > 0) ctx.drawImage(images.spike, spk.x, spk.y-camY, 28, 18);
      else { ctx.fillStyle="#aaa"; ctx.beginPath(); ctx.moveTo(spk.x, spk.y-camY+18); ctx.lineTo(spk.x+14, spk.y-camY); ctx.lineTo(spk.x+28, spk.y-camY+18); ctx.closePath(); ctx.fill(); }
    }
    for(let f of level.foods) {
      if(images.food.complete && images.food.naturalWidth > 0) ctx.drawImage(images.food, f.x, f.y-camY, 32, 32);
      else { ctx.fillStyle="#f3d725"; ctx.beginPath(); ctx.arc(f.x+16, f.y-camY+16, 15, 0, Math.PI*2); ctx.fill(); }
    }
    if(images.finish.complete && images.finish.naturalWidth > 0) ctx.drawImage(images.finish, level.finish.x, level.finish.y-camY, 44, 44);
    else { ctx.fillStyle="#f00"; ctx.fillRect(level.finish.x, level.finish.y-camY, 44, 44);}
    if(images.grass.complete && images.grass.naturalWidth > 0) ctx.drawImage(images.grass, 0, LEVEL_HEIGHT-60-camY, 1600, 60);
    else { ctx.fillStyle="#3c9e2f"; ctx.fillRect(0, LEVEL_HEIGHT-60-camY, 1600, 60);}
    // Kedi animasyonu: 
    let img=null;
    if(player.dir==='left') {
      if(!player.onGround) img = images.org3;
      else if ((keys.a || keys.d) && Math.abs(player.dx)>0.1 && player.onGround) img = walkFrame==0 ? images.org1 : images.org2;
      else img = images.org1;
    } else if(player.dir==='right') {
      if(!player.onGround) img = images.flip3;
      else if ((keys.a || keys.d) && Math.abs(player.dx)>0.1 && player.onGround) img = walkFrame==0 ? images.flip1 : images.flip2;
      else img = images.flip1;
    }
    if(img && img.complete && img.naturalWidth > 0) ctx.drawImage(img, player.x, player.y-camY, player.w, player.h);
    else { ctx.fillStyle="#f90"; ctx.fillRect(player.x, player.y-camY, player.w, player.h);}
    if(player.canEat) {
      ctx.fillStyle="#fff"; ctx.font="20px sans-serif"; ctx.strokeStyle="#222"; ctx.lineWidth=3;
      ctx.strokeText("S ile mama ye!", player.x-10, player.y-camY-16); ctx.fillText("S ile mama ye!", player.x-10, player.y-camY-16);
    }
  }

  function collide(a,b) { return rectCollide(a.x,a.y,a.w,a.h,b.x,b.y,b.w,b.h);}
  function rectCollide(ax,ay,aw,ah, bx,by,bw,bh) { return ax < bx+bw && ax+aw > bx && ay < by+bh && ay+ah > by;}
  function updateUI() {
    let healthEl = document.getElementById("healthtxt");
    let foodEl = document.getElementById("foodtxt");
    let barEl = document.getElementById("healthbar");
    if (!healthEl || !foodEl || !barEl) return;
    let health = Math.max(0,Math.round(player.health));
    healthEl.innerText = "Can: "+health;
    foodEl.innerText = "Mama: "+player.food;
    let percent = Math.max(0,Math.min(1,player.health/100));
    barEl.style.width = (percent*100*2.2)+"px";
    barEl.style.background = percent>0.5?"#28d66a":(percent>0.2?"#f7dc4a":"#e33d3d");
  }
}