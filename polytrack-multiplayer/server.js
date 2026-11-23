const http = require("http");
const crypto = require("crypto");
const { WebSocketServer, WebSocket } = require("ws");

const PORT = process.env.PORT || 10000;
const rooms = new Map();
const clients = new Map();
const CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function makeCode() {
  let code;
  do {
    code = Array.from({length: 5}, () => CODE_CHARS[crypto.randomInt(CODE_CHARS.length)]).join("");
  } while (rooms.has(code));
  return code;
}
function send(ws, data) {
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}
function roomSnapshot(room) {
  return [...room.players.values()].map(p => ({id:p.id, name:p.name, state:p.state}));
}
function broadcast(room, data, except) {
  for (const p of room.players.values()) if (p.ws !== except) send(p.ws, data);
}
function leave(ws) {
  const p = clients.get(ws);
  if (!p) return;
  clients.delete(ws);
  const room = rooms.get(p.room);
  if (!room) return;
  room.players.delete(p.id);
  broadcast(room, {type:"player-left", id:p.id, players:roomSnapshot(room)});
  if (!room.players.size) rooms.delete(p.room);
}
const server = http.createServer((req,res) => {
  if (req.url === "/health") { res.writeHead(200, {"content-type":"application/json"}); return res.end(JSON.stringify({ok:true, service:"lerncampus-polytrack-multiplayer"})); }
  res.writeHead(200, {"content-type":"application/json"}); res.end(JSON.stringify({service:"LernCampus Poly Track Multiplayer", status:"online"}));
});
const wss = new WebSocketServer({server, maxPayload: 4096});
wss.on("connection", ws => {
  ws.on("message", raw => {
    let msg;
    try { msg = JSON.parse(raw.toString()); } catch { return send(ws,{type:"error",message:"Ungültige Nachricht."}); }
    if (msg.type === "create-room") {
      if (clients.has(ws)) return;
      const code = makeCode(), id = crypto.randomUUID();
      const room = {players:new Map()};
      const player = {id, name:String(msg.name || "Spieler").slice(0,18), ws, state:null, room:code};
      room.players.set(id, player); rooms.set(code, room); clients.set(ws, player);
      return send(ws,{type:"room-created",code,playerId:id,players:roomSnapshot(room)});
    }
    if (msg.type === "join-room") {
      if (clients.has(ws)) return;
      const code = String(msg.code || "").toUpperCase().replace(/[^A-Z0-9]/g,"").slice(0,5);
      const room = rooms.get(code);
      if (!room) return send(ws,{type:"error",message:"Raum nicht gefunden. Prüfe den Einladungscode."});
      if (room.players.size >= 8) return send(ws,{type:"error",message:"Der Raum ist voll (maximal 8 Spieler)."});
      const id = crypto.randomUUID();
      const player = {id,name:String(msg.name || "Spieler").slice(0,18),ws,state:null,room:code};
      room.players.set(id,player); clients.set(ws,player);
      send(ws,{type:"room-joined",code,playerId:id,players:roomSnapshot(room)});
      broadcast(room,{type:"player-joined",player:{id,name:player.name,state:null},players:roomSnapshot(room)},ws);
      return;
    }
    const player = clients.get(ws);
    if (!player) return send(ws,{type:"error",message:"Erstelle oder betrete zuerst einen Raum."});
    const room = rooms.get(player.room);
    if (!room) return leave(ws);
    if (msg.type === "state") {
      const s = msg.state;
      if (!s || typeof s !== "object") return;
      const nums = ["x","y","z","rotation","speed"];
      const state = {};
      for (const k of nums) if (Number.isFinite(s[k])) state[k] = Math.max(-100000,Math.min(100000,s[k]));
      player.state = state;
      broadcast(room,{type:"player-state",id:player.id,state},ws);
    } else if (msg.type === "ping") send(ws,{type:"pong",at:msg.at});
    else if (msg.type === "leave-room") { leave(ws); send(ws,{type:"left"}); }
  });
  ws.on("close",()=>leave(ws));
  ws.on("error",()=>leave(ws));
});
server.listen(PORT,"0.0.0.0",()=>console.log("Poly Track multiplayer server listening on",PORT));
