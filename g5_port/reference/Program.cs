// Evaluation-only adapter. The upstream G5 policy and data are not rewritten here.
// Pinned upstream: 251d43dcea7a1a034b5759402e3a116b57b1e6c5 (MIT).
using System;
using System.IO;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using G5.Logic;
using G5.Logic.Estimators;
using ActionType = G5.Logic.ActionType;

class Program
{
    static readonly TextWriter Wire = Console.Out;
    static readonly JsonSerializerOptions JO = new JsonSerializerOptions { IncludeFields = true };
    static OpponentModeling om;
    static BotGameState gs;
    static int hero, n, hand, stack, bb, calls;
    static int[] streetBets;
    static int[] seatMap;
    static int boardCount;
    static readonly FieldInfo ActorField = typeof(BotGameState).GetField("_playerToActInd", BindingFlags.NonPublic | BindingFlags.Instance);
    static int Int(JsonElement e,string k)=>e.GetProperty(k).GetInt32();
    static int[] Ints(JsonElement e,string k)=>e.GetProperty(k).EnumerateArray().Select(v=>v.GetInt32()).ToArray();
    static string[] Strings(JsonElement e,string k)=>e.GetProperty(k).EnumerateArray().Select(v=>v.GetString()).ToArray();
    static void Log(object x) { Console.Error.WriteLine("G5AUDIT " + JsonSerializer.Serialize(x, JO)); }
    static void Write(object x) { Wire.WriteLine(JsonSerializer.Serialize(x, JO)); Wire.Flush(); }
    static void Actor(int id)
    {
        if(gs.getPlayerToActInd()!=id)
        {
            Log(new { kind="actor_resync", hand, expected=gs.getPlayerToActInd(), actual=id });
            // MAC is authoritative about who may act (including short-all-in rules).
            ActorField.SetValue(gs,id);
        }
    }
    static OpponentModeling Load(int table)
    {
        var opts=new OpponentModeling.Options {recentHandsCount=1000};
        return new OpponentModeling(table==2?"full_stats_list_hu.bin":"full_stats_list_6max.bin", (TableType)table, opts);
    }
    static void Accept(JsonElement e)
    {
        string type=e.GetProperty("type").GetString();
        if(type=="hello")
        {
            hero=Int(e,"player"); n=Int(e,"num_players"); stack=Int(e,"stack"); bb=Ints(e,"blinds")[1];
            om=Load(n==2?2:6);
            gs=new BotGameState(Enumerable.Range(0,n).Select(i=>"mac_player_"+i).ToArray(),Enumerable.Repeat(stack,n).ToArray(),hero,0,bb,PokerClient.Acpc,(TableType)(n==2?2:6),new ModelingEstimator(om,PokerClient.Acpc));
            Log(new {kind="loaded_original", upstream="251d43dcea7a1a034b5759402e3a116b57b1e6c5", n,hero,stack,bb});
        }
        else if(type=="hand_start")
        {
            hand=Int(e,"hand"); seatMap=Ints(e,"players"); streetBets=new int[n]; boardCount=0;
            var stacks=Ints(e,"stacks");
            for(int s=0;s<n;s++)gs.getPlayers()[seatMap[s]].SetStackSize(stacks[s]);
            gs.setButtonInd(seatMap[Int(e,"button")]); gs.startNewHand();
            var h=Strings(e,"hole"); gs.dealHoleCards(new Card(h[0]),new Card(h[1]));
            streetBets[seatMap[n==2?0:1]]=bb/2; streetBets[seatMap[n==2?1:2]]=bb;
        }
        else if(type=="action")
        {
            seatMap=Ints(e,"players"); int id=seatMap[Int(e,"seat")]; Actor(id);
            string a=e.GetProperty("action").GetString(); int amount=Int(e,"amount");
            if(a=="fold")gs.playerFolds();
            else if(a=="check" || a=="call") { gs.playerCheckCalls(); streetBets[id]+=amount; }
            else if(a=="raise" || a=="bet") { int by=amount-streetBets[id]; gs.playerBetRaisesBy(by); streetBets[id]=amount; }
            else throw new Exception("Unknown public action "+a);
        }
        else if(type=="street")
        {
            var board=Strings(e,"board");
            gs.goToNextStreet(board.Skip(boardCount).Select(c=>new Card(c)).ToList());
            boardCount=board.Length; Array.Clear(streetBets,0,n);
        }
        else if(type=="hand_end")
        {
            seatMap=Ints(e,"players"); var deltas=Ints(e,"deltas");
            var winnings=new List<int>(new int[n]);
            for(int s=0;s<n;s++)winnings[seatMap[s]]=deltas[s]+gs.getPlayers()[seatMap[s]].MoneyInPot;
            if(winnings.Any(x=>x<0))throw new Exception("Negative gross winnings: state adapter mismatch");
            gs.finishHand(winnings); om.addHand(gs.getCurrentHand());
        }
        else if(type=="act")
        {
            seatMap=Ints(e,"players"); Actor(hero);
            var stacks=Ints(e,"stacks"); var bets=Ints(e,"street_bets"); var folded=e.GetProperty("folded").EnumerateArray().Select(x=>x.GetBoolean()).ToArray();
            for(int s=0;s<n;s++)
            {
                int id=seatMap[s]; var p=gs.getPlayers()[id];
                if(p.Stack!=stacks[s] || streetBets[id]!=bets[s] || (p.StatusInHand==Status.Folded)!=folded[s])
                    throw new Exception($"State mismatch hand {hand} seat {s} nativeStack {p.Stack} MAC {stacks[s]} nativeBet {streetBets[id]} MACbet {bets[s]}");
            }
            if(gs.potSize()!=Int(e,"pot") || gs.getAmountToCall()!=Int(e,"to_call"))throw new Exception("Pot/call mismatch");
            var watch=Stopwatch.StartNew(); var d=gs.calculateHeroAction(); calls++; watch.Stop();
            string action; int amount=0; int ownSeat=Int(e,"seat");
            if(d.actionType==ActionType.Fold)action=Int(e,"to_call")==0?"check":"fold";
            else if(d.actionType==ActionType.Check || d.actionType==ActionType.Call)action=Int(e,"to_call")==0?"check":"call";
            else if(d.actionType==ActionType.Raise || d.actionType==ActionType.Bet || d.actionType==ActionType.AllIn)
            {
                if(!e.GetProperty("can_raise").GetBoolean())action=Int(e,"to_call")==0?"check":"call";
                else { action="raise"; amount=Math.Clamp(bets[ownSeat]+d.byAmount,Int(e,"min_raise_to"),Int(e,"max_raise_to")); }
            }
            else throw new Exception("Unexpected original decision "+d.actionType);
            Log(new {kind="decision",hand,street=e.GetProperty("street").GetString(),calls,elapsed_ms=watch.Elapsed.TotalMilliseconds,cc_ev=d.checkCallEV,br_ev=d.betRaiseEV,original_action=d.actionType.ToString(),by=d.byAmount,action,amount,stack=stacks[ownSeat],pot=Int(e,"pot"),source_call="BotGameState.calculateHeroAction"});
            Write(action=="raise"?(object)new {action,amount}:new {action});
        }
        else if(type=="match_end") { Log(new {kind="match_end",calls}); gs?.Dispose(); gs=null; }
        else if(type!="blinds")throw new Exception("Unknown message "+type);
    }
    static object Gauss(GaussianDistribution g)=>new {mean=g.Mean,sigma=g.Sigma};
    static object AD(EstimatedAD a)=>new {br=Gauss(a.BetRaise),cc=Gauss(a.CheckCall),fold=Gauss(a.Fold),prior=a.PriorSamples,updates=a.UpdateSamples};
    static object Model(PlayerModel m)=>new {vpip=Gauss(m.VPIP),pfr=Gauss(m.PFR),wtp=Gauss(m.WTP),agg=Gauss(m.AGG),pre=m.PreFlopAD.Select(AD).ToArray(),post=m.PostFlopAD.Select(AD).ToArray()};
    static object Field(object obj,string name)=>obj.GetType().GetField(name,BindingFlags.NonPublic|BindingFlags.Public|BindingFlags.Instance).GetValue(obj);
    static void Export(string outdir)
    {
        Directory.CreateDirectory(outdir);
        foreach(int table in new[]{2,6})
        {
            var model=Load(table); var population=model.FullStatsList;
            var bases=(IEnumerable)Field(model,"_baseModels"); var baseRows=new List<object>();
            foreach(var b in bases)baseRows.Add(new {vpip=Gauss((GaussianDistribution)Field(b,"VPIP")),pfr=Gauss((GaussianDistribution)Field(b,"PFR")),wtp=Gauss((GaussianDistribution)Field(b,"WTP")),agg=Gauss((GaussianDistribution)Field(b,"Aggression"))});
            var priors=new Dictionary<string,object>();
            foreach(string name in new[]{"vpip","pfr","wtp","aggression"})priors[name]=Field(Field(model,"_"+name+"Prior"),"distribution");
            var cases=new List<object>();
            cases.Add(new {index=-1,model=Model(model.estimatePlayerModel(new PlayerStats("unseen",PokerClient.Acpc,(TableType)table)))});
            foreach(int i in new[]{0,1,13,107,997,population.Count-1})cases.Add(new {index=i,model=Model(model.estimatePlayerModel(population[i]))});
            File.WriteAllText(Path.Combine(outdir,"oracle_"+table+".json"),JsonSerializer.Serialize(new {table,population=population.Count,priors,bases=baseRows,cases},JO));
        }
    }
    static int Main(string[] args)
    {
        Console.SetOut(Console.Error);
        try
        {
            if(args.Length>0 && args[0]=="--export") { Export(args.Length>1?args[1]:"oracle"); return 0; }
            string line; while((line=Console.ReadLine())!=null) { using var doc=JsonDocument.Parse(line); Accept(doc.RootElement); }
            gs?.Dispose(); return 0;
        }
        catch(Exception ex) { Console.Error.WriteLine(ex.ToString()); return 1; }
    }
}
