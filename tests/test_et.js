#!/usr/bin/env node
/* ET helper tests (P1). Run under several TZ values: TZ=Asia/Tokyo node tests/test_et.js
   Covers DST instants, BTC close labels, holidays/early closes, and the holiday-list expiry guard (fails within 60 days of the list running out). */
const fs=require('fs'),path=require('path');const R=path.join(__dirname,'..');
global.window=global;eval(fs.readFileSync(path.join(R,'assets/js/et.js'),'utf8'));const E=window.ET;
let n=0,f=0;const chk=(name,ok,info)=>{n++;if(!ok){f++;console.log('FAIL',name,info===undefined?'':JSON.stringify(info));}else console.log('PASS',name);};
const t=s=>E.time(new Date(s));
chk('fall-back 2026-11-01 05:59Z = 1:59 AM ET (EDT)',t('2026-11-01T05:59:00Z')==='1:59 AM ET',t('2026-11-01T05:59:00Z'));
chk('fall-back 2026-11-01 06:01Z = 1:01 AM ET (EST)',t('2026-11-01T06:01:00Z')==='1:01 AM ET',t('2026-11-01T06:01:00Z'));
chk('2026-11-02 23:30Z = 6:30 PM ET',t('2026-11-02T23:30:00Z')==='6:30 PM ET');
chk('spring-forward 2027-03-14 06:59Z = 1:59 AM ET',t('2027-03-14T06:59:00Z')==='1:59 AM ET');
chk('spring-forward 2027-03-14 07:01Z = 3:01 AM ET',t('2027-03-14T07:01:00Z')==='3:01 AM ET');
chk('abbr EDT in Oct',E.abbr(new Date('2026-10-23T16:00:00Z'))==='EDT');chk('abbr EST in Nov',E.abbr(new Date('2026-11-02T16:00:00Z'))==='EST');
[['2026-10-30','8 PM ET'],['2026-10-31','8 PM ET'],['2026-11-01','7 PM ET'],['2026-11-02','7 PM ET'],['2027-03-13','7 PM ET'],['2027-03-14','8 PM ET']].forEach(([d,l])=>chk('btcCloseLabel '+d+' = '+l,E.btcCloseLabel(d)===l,E.btcCloseLabel(d)));
chk('today() is the New York date at 03:30Z (still previous day ET)',E.today(new Date('2026-10-24T03:30:00Z'))==='2026-10-23');
chk('Thanksgiving 2026 holiday, not a session',E.holiday('2026-11-26')&&!E.session('2026-11-26'));
chk('Sat not a session',!E.session('2026-10-24'));chk('Fri Oct 23 is a session',E.session('2026-10-23'));
chk('early close Nov 27 2026 closeMin 780',E.closeMin('2026-11-27')===780);chk('early close Dec 24 2026',E.closeMin('2026-12-24')===780);
chk('early close Nov 26 2027',E.closeMin('2027-11-26')===780);chk('normal day closeMin 960',E.closeMin('2026-10-23')===960);chk('holiday closeMin 0',E.closeMin('2026-11-26')===0);
chk('day() no TZ shift',E.day('2026-10-22')==='Oct 22, 2026');
/* the three holiday lists must agree */
const y=fs.readFileSync(path.join(R,'.github/workflows/prices.yml'),'utf8'),g=fs.readFileSync(path.join(R,'tools/recap_gen.py'),'utf8'),e=fs.readFileSync(path.join(R,'assets/js/et.js'),'utf8');
const P=(y.match(/NYSE_HOLIDAYS = \{([^}]*)\}/)[1].match(/\d{4}-\d\d-\d\d/g)||[]).sort().join(),G=(g.match(/HOL = \{([^}]*)\}/)[1].match(/\d{4}-\d\d-\d\d/g)||[]).sort().join(),J=(e.match(/var HOL=\{([^}]*)\}/)[1].match(/\d{4}-\d\d-\d\d/g)||[]).sort().join();
chk('holiday lists identical in et.js, prices.yml, recap_gen.py',P===J&&G===J);
/* expiry guard: KNOWN LIMIT, the lists end with 2027. Fails 60 days before the last listed year ends. Override "now" with ET_TEST_NOW for testing. */
const last=J.split(',').pop().slice(0,4),end=Date.parse((+last)+'-12-31T23:59:59-05:00'),now=process.env.ET_TEST_NOW?Date.parse(process.env.ET_TEST_NOW):Date.now();
chk('holiday list valid for >= 60 more days (ends '+last+'-12-31)',end-now>=60*864e5,{daysLeft:Math.floor((end-now)/864e5)});
console.log('ET TESTS',n,'FAIL',f,'TZ',process.env.TZ||'(system)');process.exit(f?1:0);
