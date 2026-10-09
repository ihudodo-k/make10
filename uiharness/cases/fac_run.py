# -*- coding: utf-8 -*-
"""階乗を重ねない（7.9・GAME-SPEC 2-4・4-2）。

「数字 ! ) !」の ) を外す・別の枠へ運ぶ・タップ配置で消すと、! が隣り合って「!!」になっていた
（置くときは canPut が止めるが、外した後の列は誰も見ていなかった）。
- 外した・運んだ後に !! が残っていたら、後ろの ! も一緒に外す（dropFacRun）。手数には数えない
- parse は ! の連続を読まない（!! のある列は「この式は計算できません」）
- ( 3! )! の括弧は、要る括弧なので薄くしない
操作は本物のマウス（CDP）で行う。最後に、置く・外す・運ぶを数万手ぶん歩いて、どの列も決まりを満たすことを見る。
"""
import time

NAME = "階乗を重ねない（!! を作らせない）"

PLACE = """
window.__place=function(s){
  clearAll();let i=0;
  for(const ch of s.replace(/\\s+/g,'')){
    if(/[0-9]/.test(ch)){i++;}
    else if(ch==='('){put('lp',i);i++;}
    else if(ch===')'){put('rp',i);i++;}
    else if(ch==='!'){put('!',i);i++;}
    else {put(ch,i);i++;}
  }
  render();
  return __toks();
};
window.__toks=()=>T().map(t=>t.t==='num'?'n':t.t==='op'?t.v:t.t==='fac'?'!':t.t==='lp'?'(':')').join(' ');
window.__digits=d=>{T().filter(t=>t.t==='num').forEach((t,i)=>{t.v=+d[i]})};
"""
# 置く・外す・運ぶを、ページの本物の関数で、操作の処理（onUp・タップ）と同じ順に呼んで歩く
WALK = r"""(function(steps){
  const CH={num:'n',op:'o',fac:'f',lp:'(',rp:')'}, KIND={op:'+',fac:'!',lp:'lp',rp:'rp'};
  const ser=()=>T().map(t=>CH[t.t]).join('');
  const bad=s=>{if(s.includes('ff'))return '!!';
    if((s.match(/\(/g)||[]).length>4||(s.match(/\)/g)||[]).length>4)return '括弧が 4 つを超える';
    for(let i=0;i<s.length;i++){const a=s[i-1],c=s[i],b=s[i+1];
      if(c==='f'&&!(a==='n'||a===')'))return '! の前';
      if(c==='('&&!(b==='n'||b==='('))return '( の後';
      if(c===')'&&!(a==='n'||a==='f'||a===')'))return ') の前';
      if(c==='o'&&(!(a==='n'||a==='f'||a===')')||!(b==='n'||b==='(')))return '演算子の前後'}
    return null};
  let seed=20261010;const rnd=n=>{seed=(seed*1103515245+12345)%2147483648;return seed%n};
  const seen=new Set(),broken=[];let cut=0,unread=0;
  clearAll();
  for(let k=0;k<steps;k++){
    if(k%400===0)clearAll();
    const movable=T().filter(t=>t.t!=='num'), r=rnd(10);
    if(r<5||!movable.length){                       // 置く
      const kind=['+','!','lp','rp','!','rp','lp'][rnd(7)], live=[...livePositions(kind)];
      if(live.length)put(kind,live[rnd(live.length)]);
    }else{
      const tk=movable[rnd(movable.length)], n0=T().length;
      if(r<8){dropTok(tk.id);dropFacRun();if(T().length<n0-1)cut++}          // 外す（外へ出す・タップで消す）
      else{const live=[...livePositions(KIND[tk.t])];                        // 運ぶ
        if(live.length){const p=live[rnd(live.length)],was=T().findIndex(x=>x.id===tk.id),ins=was<p?p-1:p;
          dropTok(tk.id);put(KIND[tk.t],ins);dropFacRun();if(T().length<n0)cut++}}
    }
    const s=ser();seen.add(s);const b=bad(s);if(b&&broken.length<5)broken.push([s,b]);
    // 演算子が 3 つそろっていて括弧が合っている列は、式として読める（!! が無いので）
    if(s.split('o').length===4){const m=match();if(Object.values(m).every(x=>x!==null)&&!parse(T()))unread++}
  }
  clearAll();render();
  return {broken,states:seen.size,cut,unread}})(__STEPS__)"""


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)


def drag(ui, src, dest):
    """src（セレクタ）をつまんで、dest（セレクタか座標を返す関数）で離す"""
    x, y = center(ui, src)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseMoved", x, y - 6)
    time.sleep(0.45)                                   # 枠が開き終わるのを待つ
    tx, ty = dest() if callable(dest) else center(ui, dest)
    for k in range(1, 6):
        mouse(ui, "mouseMoved", x + (tx - x) * k / 5, (y - 6) + (ty - (y - 6)) * k / 5)
        time.sleep(0.03)
    mouse(ui, "mouseReleased", tx, ty)
    time.sleep(0.5)


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.ev("go('home'); start('free')")
    ui.ev(PLACE)
    BASE = "( n n ! ) ! n n"
    above = lambda: ui.ev("(()=>{const r=$('field').getBoundingClientRect();return [r.left+r.width/2,r.top-70]})()")  # noqa: E731
    RP = "#expr .tok.rp"

    # ══ 報告の手順: ( 1 2! )! 3 4 の ) を、盤の外へ出す ══
    ui.check("組んだ形（置くだけでは !! にならない）", ui.ev("__place('(12!)!34')"), BASE)
    ui.check("! の隣には ! を置けない（canPut）", ui.ev("[canPut('!',4),canPut('!',6)]"), [False, False])
    m0 = ui.ev("moves")
    drag(ui, RP, above)
    ui.check(") を盤の外へ出す: 後ろの ! も一緒に外れて、!! が残らない", ui.ev("__toks()"), "( n n ! n n")
    ui.check("外へ出すのは手数に数えない（一緒に消えた ! も）", ui.ev("moves") - m0, 0)
    ui.check_no_errors(") を外へ出して JS エラー 0")

    # ══ ) を別の枠へ運ぶ ══
    ui.ev("__place('(12!)!34')")
    m0 = ui.ev("moves")
    drag(ui, RP, ".zone.live[data-p='8']")
    ui.check(") を式の右端へ運ぶ: 運び終えた後に、後ろの ! が外れる（運んだ ) は残る）", ui.ev("__toks()"), "( n n ! n n )")
    ui.check("運ぶのは 1 手（一緒に消えた ! は数えない）", ui.ev("moves") - m0, 1)

    # ══ 元の場所へ戻しただけでは、! は消えない ══
    ui.ev("__place('(12!)!34')")
    live = ui.ev("(()=>{const rp=T().find(t=>t.t==='rp');return [T().indexOf(rp),[...livePositions('rp')]]})()")
    ui.check("運べる枠に、今の場所のすぐ右がある（そこへ置くと列は変わらない）", [live[0], live[0] + 1 in live[1]], [4, True])
    drag(ui, RP, ".zone.live[data-p='5']")
    ui.check(") をつまんで元の場所へ戻す: 列はそのまま（! は 2 つとも残る）", ui.ev("__toks()"), BASE)
    drag(ui, RP, lambda: center(ui, RP))
    ui.check(") をつまんで、そのまま離す: 列はそのまま", ui.ev("__toks()"), BASE)

    # ══ タップ配置で消す ══
    ui.ev("__place('(12!)!34');tapMode=true")
    x, y = center(ui, RP)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseReleased", x, y)
    time.sleep(0.3)
    ui.check("タップ配置で ) を押して消す: 後ろの ! も一緒に外れる", ui.ev("__toks()"), "( n n ! n n")
    ui.ev("tapMode=false")

    # ══ ほかの外し方は、今までどおり ══
    ui.ev("__place('(12!)!34')")
    drag(ui, "#expr .tok.lp", above)
    ui.check("( を外へ出す: ( だけが外れる", ui.ev("__toks()"), "n n ! ) ! n n")
    ui.ev("__place('(12!)!34')")
    drag(ui, "#expr .tok.fac", above)
    ui.check("内側の ! を外へ出す: その ! だけが外れる", ui.ev("__toks()"), "( n n ) ! n n")
    ui.ev("__place('(1+2)!34')")
    drag(ui, RP, above)
    ui.check("! が 1 つだけのとき: ) を外しても ! は残る", ui.ev("__toks()"), "( n + n ! n n")
    ui.check("入れ子: ( ( 1! )! )! の内側の ) を外すと、! が 1 つ外れるだけ",
             ui.ev("(()=>{__place('((1!)!)!234');const rp=T().find(t=>t.t==='rp');dropTok(rp.id);dropFacRun();return __toks()})()"),
             "( ( n ! ) ! n n n")
    ui.check("dropFacRun は、!! が無ければ何も外さず、位置もそのまま返す",
             ui.ev("(()=>{__place('(12!)!34');const f=dropFacRun();return [__toks(),[0,3,7,null].map(f)]})()"),
             [BASE, [0, 3, 7, None]])
    ui.check("dropFacRun が返す関数は、外した ! より後ろの位置を 1 つ詰める",
             ui.ev("(()=>{__place('(12!)!34');dropTok(T().find(t=>t.t==='rp').id);const f=dropFacRun();"
                   "return [0,3,4,5,6,null].map(f)})()"), [0, 3, 4, 4, 5, None])

    # ══ !! のある列は、式として読まない ══
    ui.ev("__place('1!+2+3+4');__digits('6823')")
    ui.check("parse: 3 ! ! は読まない。( 3! )! は読めて 720",
             ui.ev("(()=>{const n={id:1,t:'num',v:3},f=()=>({id:9,t:'fac'}),v=a=>a?String(ev(a).n):null;"
                   "return [v(parse([n,f(),f()])),v(parse([{id:2,t:'lp'},n,f(),{id:3,t:'rp'},f()])),v(parse([n,f()]))]})()"),
             [None, "720", "6"])
    ui.ev("__place('6!+8+2-3!');T().push({id:uid++,t:'fac'});render()")
    ui.check("!! を直に組んだ列（6! + 8 + 2 − 3!!）: 計算できない扱いで、正解にならない",
             [ui.ev("__toks()"), ui.text("eq"), ui.text("sub"), ui.ev("solved"), ui.ev("$('eq').classList.contains('hit')")],
             ["n ! + n + n - n ! !", "この式は計算できません", "0 で割る、階乗が大きすぎる、などの理由です", False, False])

    # ══ ( 3! )! の括弧は、要る括弧なので薄くしない ══
    ui.ev("__place('6!+8+2+(3!)!');__digits('6823');render()")
    ui.check("6! + 8 + 2 + ( 3! )!: 値は 1450。括弧は薄くならない（外すと !! になり、同じ式として読めないため）",
             [ui.text("eq"), ui.ev("document.querySelectorAll('#expr .tok.dead').length")], ["1450", 0])
    ui.ev("__place('(6!)+8+2+3');__digits('6823');render()")
    ui.check("( 6! ) + 8 + 2 + 3: 要らない括弧は、今までどおり薄くなる",
             [ui.text("eq"), ui.ev("document.querySelectorAll('#expr .tok.dead').length")], ["733", 2])

    # ══ 数万手ぶん歩いて、どの列も決まりを満たす ══
    w = ui.ev(WALK.replace("__STEPS__", "40000"))
    ui.check("置く・外す・運ぶを 4 万手: 決まりに反する列（!! など）が 1 つも出ない", w["broken"], [])
    ui.check("4 万手のあいだ、演算子が 3 つそろって括弧が合った列は、どれも式として読める", w["unread"], 0)
    ui.check("歩きが空振りしていない（通った列が 5,000 種類より多く、! を一緒に外した回が 100 回より多い）",
             [w["states"] > 5000, w["cut"] > 100], [True, True])
    ui.check_no_errors()
