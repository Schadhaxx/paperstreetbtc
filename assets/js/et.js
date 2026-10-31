/* Site-wide Eastern Time helper. Every user-visible date/time on paperstreetbtc.com goes through here (America/New_York, EDT/EST automatic). */
(function(){
  var Z='America/New_York';
  function parts(d,o){var r={};new Intl.DateTimeFormat('en-US',Object.assign({timeZone:Z,hourCycle:'h23'},o)).formatToParts(d||new Date()).forEach(function(p){r[p.type]=p.value;});return r;}
  /* NYSE full-day holidays (same list as tools/recap_gen.py:17) */
  var HOL={'2026-01-01':1,'2026-01-19':1,'2026-02-16':1,'2026-04-03':1,'2026-05-25':1,'2026-06-19':1,'2026-07-03':1,'2026-09-07':1,'2026-11-26':1,'2026-12-25':1,
           '2027-01-01':1,'2027-01-18':1,'2027-02-15':1,'2027-03-26':1,'2027-05-31':1,'2027-06-18':1,'2027-07-05':1,'2027-09-06':1,'2027-11-25':1,'2027-12-24':1,
           '2028-01-17':1,'2028-02-21':1,'2028-04-14':1,'2028-05-29':1,'2028-06-19':1,'2028-07-04':1,'2028-09-04':1,'2028-11-23':1,'2028-12-25':1};
  /* NYSE early closes (1:00 PM ET), minutes after midnight ET */
  var EARLY={'2026-11-27':780,'2026-12-24':780,'2027-11-26':780,'2028-07-03':780,'2028-11-24':780};
  var ET={
    zone:Z,
    holiday:function(iso){return !!HOL[iso||ET.today()];},
    /* NYSE session day in ET (weekday, not a holiday) */
    session:function(iso){iso=iso||ET.today();var w=new Date(iso+'T12:00:00Z').getUTCDay();return w>0&&w<6&&!HOL[iso];},
    /* regular-session close in minutes ET for a session day (960 = 4:00 PM, 780 = 1:00 PM early close); 0 if no session */
    closeMin:function(iso){iso=iso||ET.today();return ET.session(iso)?(EARLY[iso]||960):0;},
    early:function(iso){return !!EARLY[iso||ET.today()];},
    /* 'YYYY-MM-DD' calendar date in New York */
    today:function(d){return new Intl.DateTimeFormat('en-CA',{timeZone:Z}).format(d||new Date());},
    /* {y,mo,d,h,mi,wd} in New York */
    now:function(d){var p=parts(d,{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',weekday:'short'});return {y:+p.year,mo:+p.month,d:+p.day,h:+p.hour%24,mi:+p.minute,wd:p.weekday};},
    /* 'EDT' or 'EST' */
    abbr:function(d){return parts(d,{timeZoneName:'short'}).timeZoneName||'ET';},
    /* '4:19 PM ET' (visible label is always 'ET'; use abbr() for a tooltip) */
    time:function(d,sec){return (d||new Date()).toLocaleTimeString('en-US',{timeZone:Z,hour:'numeric',minute:'2-digit',second:sec?'2-digit':undefined})+' ET';},
    /* 'Oct 23, 4:19 PM ET' */
    stamp:function(d){return (d||new Date()).toLocaleString('en-US',{timeZone:Z,month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' ET';},
    /* ISO date string -> 'Oct 23, 2026' without any timezone shift */
    day:function(iso,yr){return new Date(iso+'T12:00:00Z').toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric',year:yr===false?undefined:'numeric'});},
    /* BTC daily close (00:00 UTC) in ET for the given UTC day: '8 PM ET' (EDT) or '7 PM ET' (EST) */
    btcCloseLabel:function(isoUtcDay){var t=isoUtcDay?new Date(Date.parse(isoUtcDay+'T00:00:00Z')+864e5):new Date(Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate()+1));
      return t.toLocaleTimeString('en-US',{timeZone:Z,hour:'numeric'})+' ET';}
  };
  window.ET=ET;
})();
