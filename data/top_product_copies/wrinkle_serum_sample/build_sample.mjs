import fs from 'node:fs/promises';
import { Workbook } from '@oai/artifact-tool';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const date = '2026-10-13';
const rankUrl = 'https://www.oliveyoung.co.kr/store/main/getBestList.do?dispCatNo=900000100100001&fltDispCatNo=10000010001';
const oy = id => `https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=${id}`;
const sources = {
  anua: 'https://m.anua.kr/product/detail.html?product_no=359',
  primera: 'https://prd-ko-kr.primerabeauty.com/kr/ko/product/vitatinol-bouncy-lift-serum.html',
  celimax: 'https://celimax.co.kr/product/레티날-샷-타이트닝-부스터-15ml-스팟크림/70/',
  ongredients: 'https://ongredients.com/product/detail.html?cate_no=90&display_group=1&product_no=89',
};
const common = {
  platform: '올리브영', category: '주름 개선 기능성 세럼·앰플 후보',
  collected_date: date, ranking_type: '오늘의 랭킹 / 스킨케어',
  ranking_period: '페이지 명칭: 오늘의 랭킹; 실제 산정 기간 미공개',
  ranking_source_url: rankUrl, ranking_metric: '판매 랭킹이라는 플랫폼 표시; 매출 아님',
  functional_status: '기능성 표시 확인',
  functional_status_basis: '상품정보 제공고시의 심사 또는 보고 필함 표시; 식약처 등록 원본 미확인',
  rating_scale: 5, review_scope: '해당 상품 페이지 누적 리뷰; 옵션별 분리되지 않음',
  award_history: '', award_status: '미확인',
  public_product_sales: '', public_product_sales_status: '미공개', public_product_sales_source_url: '',
  sale_exposed: true, sale_event: '세일 표시; 올영세일 행사로 확정하지 않음',
  price_basis: '비로그인 상세페이지 표시가; 쿠폰·결제 혜택 별도',
  lower_copy_coverage: '전체 하단 전수 확인 아님; 확인한 원문만 채록',
};
const products = [
  {...common, product_id:'OY_A000000222698', brand:'아누아',
    product_name:'[수지세럼] 아누아 피디알엔 히알루론산 캡슐 100 세럼 30mL 기획 (+30mL 리필팩)',
    volume:'30mL + 리필 30mL', product_url:oy('A000000222698'), ranking:3,
    functional_type:'미백;주름 개선', functional_type_status:'브랜드 공식 제품 고시 확인', functional_source_url:sources.anua,
    key_ingredients:'소듐디엔에이(PDRN, 100ppm);히알루론산 계열;나이아신아마이드;아데노신',
    review_count:14035, rating:4.8, list_price_krw:58500, sale_price_krw:27500, discount_percent_displayed:52,
    price_is_from:false, bundle:'본품 30mL + 리필 30mL', coupon_exposed:'미확인',
    celebrity_badge_exposed:true, celebrity_badge_text:'수지세럼;상세 상단 수지 이미지',
    first_screen_copy:'새로운 장르의 수분광채', data_quality_note:'100은 제품명 일부이며 효과 개선율로 해석하지 않음'},
  {...common, product_id:'OY_A000000231293', brand:'프리메라',
    product_name:'[10월 올영픽/탄력광채세럼] 프리메라 비타티놀 바운시 리프트 세럼 25g 기획/단품',
    volume:'상품명 25g;기획 이미지 25g+리필25g+겔마스크1매;제공고시30g', product_url:oy('A000000231293'), ranking:8,
    functional_type:'미백;주름 개선', functional_type_status:'공식 바운시 리프트 제품 설명 기능성 아이콘 확인', functional_source_url:sources.primera,
    key_ingredients:'아스코빌글루코사이드;나이아신아마이드;레티놀;아데노신',
    review_count:6194, rating:4.8, list_price_krw:32500, sale_price_krw:23200, discount_percent_displayed:28,
    price_is_from:true, bundle:'기획 이미지:25g+리필25g+겔마스크1매;단품 옵션도 포함', coupon_exposed:true,
    celebrity_badge_exposed:'미확인', celebrity_badge_text:'', sale_event:'10월 올영픽;세일',
    first_screen_copy:'첫 화면은 플랫폼 소개;제품 소구는 그 아래 기획 구성 이미지',
    data_quality_note:'최저 표시가는 옵션 미선택 가격으로 기획 세트 가격과 동일하다고 단정 금지. 상품명25g와 고시30g 불일치. 공식 페이지 하단 구형 유스 래디언스 고시는 현재 제품 근거로 사용하지 않음'},
  {...common, product_id:'OY_A000000265385', brand:'온그리디언츠',
    product_name:'[NEW] 온그리디언츠 바쿠글로우 레티날 부스터 샷 0.2퍼센트 30ml',
    volume:'30ml', product_url:oy('A000000265385'), ranking:9,
    functional_type:'', functional_type_status:'기능성 표시 확인;주름 개선 유형의 명시적 표시 추가 확인 필요', functional_source_url:oy('A000000265385'),
    key_ingredients:'레틴알(0.2%);나이아신아마이드;바쿠치올;소듐디엔에이;아데노신',
    review_count:339, rating:5, list_price_krw:32000, sale_price_krw:25000, discount_percent_displayed:21,
    price_is_from:false, bundle:'본품30ml;기간 한정 증정 조건은 별도 안내 확인 필요', coupon_exposed:true,
    celebrity_badge_exposed:true, celebrity_badge_text:'세븐틴 에스쿱스 pick;상세 이미지',
    first_screen_copy:'앰버서더 행사 이미지;10.12-10.31',
    data_quality_note:'성분이나 주름 효능 광고만으로 기능성 유형을 확정하지 않음. 유형 확인 전 확정 주름 기능성 분포 집계에서는 제외'},
  {...common, product_id:'OY_A000000250199', brand:'셀리맥스',
    product_name:'[단독기획/모공탄력] 셀리맥스 더 비타 A 레티날 샷 타이트닝 부스터 15ml 기획(+3ml)',
    volume:'15ml + 3ml', product_url:oy('A000000250199'), ranking:10,
    functional_type:'미백;주름 개선', functional_type_status:'브랜드 공식 기능성여부 고시 확인', functional_source_url:sources.celimax,
    key_ingredients:'레틴알(0.1%);나이아신아마이드;아데노신;하이드롤라이즈드해면;펩타이드',
    review_count:5487, rating:4.8, list_price_krw:30000, sale_price_krw:23100, discount_percent_displayed:23,
    price_is_from:false, bundle:'본품15ml + 추가3ml', coupon_exposed:'미확인',
    celebrity_badge_exposed:'미확인', celebrity_badge_text:'',
    first_screen_copy:'판매랭킹 TOP.1;모공 탄력',
    data_quality_note:'상세 이미지 TOP.1은 광고에 실린 별도 주장. 관찰한 스킨케어 순위10과 구별. 공식몰 스팟 크림 표기와 플랫폼 세럼/앰플 분류가 다름'},
  {...common, product_id:'OY_A000000268161', brand:'아이오페',
    product_name:'아이오페 레티놀 레티젝션 세럼 기획 20ml (+10ml)',
    volume:'20ml + 10ml', product_url:oy('A000000268161'), ranking:30,
    functional_type:'', functional_type_status:'기능성 표시 확인;주름 개선 유형의 명시적 표시 추가 확인 필요', functional_source_url:oy('A000000268161'),
    key_ingredients:'레티놀;하이드록시피나콜론레티노에이트;나이아신아마이드;아데노신',
    review_count:3087, rating:4.8, list_price_krw:39000, sale_price_krw:29900, discount_percent_displayed:23,
    price_is_from:false, bundle:'본품20ml + 추가10ml', coupon_exposed:'미확인',
    celebrity_badge_exposed:'미확인', celebrity_badge_text:'',
    first_screen_copy:'탄력 효과',
    data_quality_note:'RX 2%는 처방 소구이며 순수 레티놀2%로 해석하지 않음. 유형 확인 전 확정 주름 기능성 분포 집계에서는 제외'},
];

const copies=[];
function copy(index,text,position,tags,numeric=false,numberKind='없음',testStatus='해당 없음',extra={}) {
  const p=products[index];
  copies.push({copy_id:`${p.product_id}_C${String(copies.filter(c=>c.product_id===p.product_id).length+1).padStart(2,'0')}`,
    product_id:p.product_id,copy_text:text,'위치':position,'문구 유형':tags,'수치 여부':numeric,
    '수치 종류':numberKind,'시험 조건 표기 여부':testStatus,judge_level:null,
    source_url:p.product_url,source_platform:'올리브영',collected_date:date,
    '시험 조건':{기간:null,대상:null,기관:null},'동반 주석':null,...extra});
}
copy(0,'피디알엔 히알루론산 캡슐 100 세럼','상품명',['성분 소구형'],true,'제품명 숫자');
copy(0,'(+30mL 리필팩)','상품명',['구성·혜택형'],true,'용량');
copy(0,'새로운 장르의 수분광채','상세 상단',['효능 서술형'],false,'없음','해당 없음',{evidence_file:'evidence/anua_detail_top.png'});
copy(0,'피디알엔 #수지세럼','상세 상단',['성분 소구형'],false,'없음','해당 없음',{evidence_file:'evidence/anua_detail_top.png','동반 주석':'유명인 소구 동반'});

copy(1,'[10월 올영픽/탄력광채세럼]','상품명',['구성·혜택형','효능 서술형'],true,'행사 월');
copy(1,'비타티놀 세럼 최다 구성 기획','상세 상단',['구성·혜택형','비교·순위형']);
copy(1,'세럼 리필 25G + 겔마스크 1매','상세 상단',['구성·혜택형'],true,'용량·구성');
copy(1,'단독 사용보다 더욱 강해지는 탄력 2배* 시너지','상세 상단',['효능 수치형','비교·순위형'],true,'효능 비교 배수','일부 확인',{
  '동반 주석':'겔 마스크 단독 사용 대비. 세럼+겔 마스크 병행 구간의 문구이며 세럼 단독 효과로 사용 금지',
  '시험 조건':{기간:null,대상:null,기관:null},test_scope:'세럼+겔 마스크 병행',
  review_note:'비교 대상 주석만 확인;기간·대상·기관은 이 채록 구간에서 미확인'});

copy(2,'레티날 부스터 샷 0.2퍼센트','상품명',['성분 소구형'],true,'성분 함량');
copy(2,'세븐틴 에스쿱스 pick','상세 상단',[],false,'없음','해당 없음',{'유형 보완 사유':'유명인 소구는 요청한 6개 유형에 해당하지 않아 빈 배열로 보존'});
copy(2,'프로바이오틱스 유래 유산균 PDRN','상세 상단',['성분 소구형'],false,'없음','해당 없음',{'동반 주석':'원료적 특성에 한함'});
copy(2,'미간 주름 완화\n14.03% 개선','상세 상단',['효능 수치형'],true,'효능 개선율','확인',{
  evidence_file:'evidence/ongredients_numeric.png',test_evidence_file:'evidence/ongredients_test_conditions.png',
  '시험 조건':{기간:'사용4주;시험2026.04.10~2026.05.29',대상:'38~59세 성인 여성21명',기관:'한국피부과학연구원'},
  '동반 주석':'개인차 있을 수 있음',review_note:'같은 효능 평가 이미지 묶음의 하단 주석 확인. 원본 시험 보고서 확보 아님'});

copy(3,'모공탄력','상품명',['효능 서술형']);
copy(3,'(+3ml)','상품명',['구성·혜택형'],true,'용량');
copy(3,'판매랭킹 TOP.1','상세 상단',['비교·순위형'],true,'광고에 표기된 순위','해당 없음',{
  evidence_file:'evidence/celimax_detail_top.png','동반 주석':'현재 관찰 순위와 다른 광고 주장. 별도 순위 기준 미확인'});
copy(3,'892% 흡수 기술','상세 상단',['효능 수치형'],true,'흡수 관련 수치','미확인',{
  evidence_file:'evidence/celimax_numeric.png',review_note:'흡수 관련 수치. 주름 개선율로 해석 금지. 대응 시험 주석을 확보하지 못해 미확인으로 기록'});
copy(3,'팔자 주름\n-18.49%','상세 상단',['효능 수치형'],true,'효능 변화율','확인',{
  evidence_file:'evidence/celimax_wrinkle_numeric.png',test_evidence_file:'evidence/celimax_test_conditions.png',
  '시험 조건':{기간:'2024.05.27~2024.06.13',대상:'성인 남녀21명',기관:'(주)스킨메드 임상시험센터'},
  '동반 주석':'개인차 있음',review_note:'깊게 패인 주름 개선 시험 주석과 연결. 원본 시험 보고서 확보 아님'});

copy(4,'(+10ml)','상품명',['구성·혜택형'],true,'용량');
copy(4,'탄력 효과','상세 상단',['효능 서술형']);
copy(4,'레티놀 RX™ 2%','상세 상단',['성분 소구형'],true,'처방 함량', '해당 없음',{
  evidence_file:'evidence/iope_numeric.png','동반 주석':'순수레티놀 800IU/g이라는 이미지 주석. 상품 제공고시880IU와 서로 다른 표기;수정·동일화하지 않음'});
copy(4,'피부 속4) 46% 더 깊숙하게5)','상세 상단',['효능 수치형','비교·순위형'],true,'흡수·도달 비교율','일부 확인',{
  evidence_file:'evidence/iope_numeric.png','동반 주석':'4)피부 표피층을 의미;5)레티젝션 미적용 대비',
  review_note:'부위·비교 대상은 확인.기간·대상·기관은 확보한 구간에서 미확인. 진피 도달 수치로 바꾸지 않음'});

const comparisons=[
  {case_id:'CMP_01',product_id:products[2].product_id,identity_basis:'동일 브랜드·제품명·레티날0.2% 본품;공통 제품명 기준 매칭.전성분의 플랫폼 간 완전 일치 미확인',
    collected_date:date,
    oliveyoung:{url:products[2].product_url,price_krw:25000,discount_percent_displayed:21,exposure:'NEW;0.2퍼센트;앰버서더 행사 이미지',bundle:'30ml 본품;증정은 별도 조건'},
    musinsa:{url:'https://www.musinsa.com/products/7073570',price_krw:28900,discount_percent_displayed:10,exposure:'0.2%;무뷰페;무배당발;첫 구매 쿠폰 별도',bundle:'상품명에 추가 구성 없음',evidence_file:'evidence/ongredients_musinsa_top.png'},
    observation:'브랜드·본품명이 같은 상품도 플랫폼 행사·배송·유명인 표현의 앞세우는 방식과 표시가가 다름',
    limitation:'실험이 아니며 가격·행사·이용자·노출량이 동시 변화.문구 단독 효과 추정 불가'},
  {case_id:'CMP_02',product_id:products[3].product_id,identity_basis:'동일 셀리맥스 레티날 샷 타이트닝 부스터15ml 본품;플랫폼별 증정 구성은 다름',
    collected_date:date,
    oliveyoung:{url:products[3].product_url,price_krw:23100,discount_percent_displayed:23,exposure:'단독기획;모공탄력',bundle:'15ml+3ml'},
    musinsa:{url:'https://www.musinsa.com/products/5142164',price_krw:29700,discount_percent_displayed:1,exposure:'모공잡티세럼팩1매 증정',bundle:'15ml+팩1매',rating:4.7,review_count:208,evidence_file:'evidence/celimax_musinsa_top.png'},
    observation:'올리브영은 효능과 추가 용량을,무신사는 팩 증정을 상품명에서 노출',
    limitation:'본품 기준 비교이며 판매 구성 전체가 고정된 비교가 아님.가격·문구의 매출 효과 추정 불가'},
];

// Author the requested tabular data with the bundled artifact-tool runtime.
const primaryColumns=['product_id','platform','category','brand','product_name','volume','collected_date','product_url'];
const columns=[...new Set([...primaryColumns,...products.flatMap(Object.keys)])];
const matrix=[columns,...products.map(p=>columns.map(c=>p[c]??null))];
const workbook=Workbook.create();
const sheet=workbook.worksheets.add('Products');
sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values=matrix;
workbook.recalculate();
console.log((await workbook.inspect({kind:'region',sheetId:'Products',range:'A1:H6',maxChars:1600,tableMaxRows:6,tableMaxCols:8})).ndjson);

// CSV export is serialized from the authored sheet values, preserving quotes/newlines.
const values=sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values;
const escape=v=>v===null||v===undefined?'':`"${String(v).replaceAll('"','""')}"`;
await fs.writeFile(path.join(root,'products.csv'),'\uFEFF'+values.map(r=>r.map(escape).join(',')).join('\r\n')+'\r\n','utf8');
await fs.writeFile(path.join(root,'copies.jsonl'),copies.map(x=>JSON.stringify(x)).join('\n')+'\n','utf8');
await fs.writeFile(path.join(root,'comparison_cases.json'),JSON.stringify(comparisons,null,2)+'\n','utf8');
await fs.writeFile(path.join(root,'source_register.json'),JSON.stringify({collected_date:date,method:'공개 페이지 브라우저 직접 열람;광고 이미지 육안 채록;대량 크롤링 없음',ranking_url:rankUrl,functional_sources:sources,product_urls:products.map(p=>p.product_url),comparison_urls:comparisons.map(c=>c.musinsa.url),scope:'5개 후보 샘플.현재 주름 유형 명시 확인3개;유형 보완2개.주름 전용 TOP5 아님',copy_selection:'대표 문구 발췌;상세 전체 전수 채록 아님',schema_extension:'요청 태그6종에 비수치 효능을 담을 수 없어 효능 서술형을 추가 제안.유명인 단독 문구는 빈 유형+보완 사유로 기록'},null,2)+'\n','utf8');

const tags=['효능 수치형','시험·검사 표방형','성분 소구형','사용감형','구성·혜택형','비교·순위형','효능 서술형'];
const typeCounts=tags.map(t=>[t,new Set(copies.filter(c=>c['문구 유형'].includes(t)).map(c=>c.product_id)).size,copies.filter(c=>c['문구 유형'].includes(t)).length]);
const summary=`# 주름 개선 세럼·앰플 문구 샘플 v0.1\n\n수집일: ${date}(한국). 제품5행 / 대표 문구${copies.length}행 / 플랫폼 비교2건. 모든 judge_level은 null. 판정기 실행·Qdrant 적재는 하지 않음.\n\n## 선정 범위와 검증 상태\n\n올리브영 오늘의 **스킨케어** 판매 랭킹에서 세럼/앰플로 분류된 상위권 후보를 목적 표집했다. 주름 전용 카테고리 TOP5나 판매량 TOP5가 아니다. 관찰 순위는 3·8·9·10·30이다. 미백 기능성일 수 있는 메디힐 마데카소사이드 더마 세럼은 주름 기능성 유형이 확인되지 않아 이 샘플에서 제외했다.\n\n**기능성 고시는5개 모두 확인했지만 주름 유형의 명시적 표시는3개만 확인했다.** 온그리디언츠·아이오페2개는 유형 공란으로 남겼다. 따라서 이 파일은 형식 검토용5개 후보 샘플이며, 확정 주름 기능성 상위5개 완료본이 아니다. 성분·효능 광고로 유형을 추정하지 않았다. 확정 집계는 주름 표시 확인3개를 기준으로 해야 한다.\n\n|제품|스킨케어 순위|표시가(원)|리뷰/평점|주름 유형|\n|---|---:|---:|---|---|\n${products.map(p=>`|${p.brand}|${p.ranking}|${p.sale_price_krw.toLocaleString()}${p.price_is_from?'~':''}|${p.review_count.toLocaleString()} / ${p.rating}|${p.functional_type?'명시 확인':'추가 확인 필요'}|`).join('\n')}\n\n랭킹 출처: [올리브영 오늘의 스킨케어 랭킹](${rankUrl}). 가격·평점·리뷰는 각 products.csv의 상품URL을 직접 열어 확인했다. 캐시 검색의 과거 가격·순위를 현재값으로 섞지 않았다.\n\n## 대표 문구의 유형 분포\n\n아래는 **후보5개에서 채록한 문구**의 분포다. 유형 복수 선택을 허용하여 합계는100%가 아니다. 0건은 전수 확인 결과의 부재가 아니라 이번 발췌에서 미채록을 뜻한다. 상세이미지 전체를 채록하지 않았으므로 시장 전체 비율로 일반화할 수 없다.\n\n|유형|사용 제품 수/5|채록 문구 수|\n|---|---:|---:|\n${typeCounts.map(r=>`|${r[0]}|${r[1]}/5|${r[2]}|`).join('\n')}\n\n**태그 보완 제안:** 요청한6종에는 ‘모공탄력’ 같은 비수치 효능 서술을 넣을 칸이 없다. 의미를 왜곡하지 않도록 효능 서술형을7번째 유형으로 제안했다. 유명인 단독 소구는 빈 배열+보완 사유로 보존했다. 정식 확장 전 이 분류를 확인하면 된다.\n\n수치 여부는 단순 숫자 존재이며 효과 수치와 같지 않다. 제품명100,함량0.2%,추가10ml,행사10월,광고TOP.1을 각각 구별했다. 원문 줄바꿈과 별표·주석 번호는 가능한 그대로 보존하고, 주변 시험조건은 별도 필드에 연결했다.\n\n## 조건 요인의 관찰\n\n- 본품 외 추가 용량·리필을 상품명에 노출한 후보는 아누아·셀리맥스·아이오페3개다. 프리메라는 기획 이미지에서 리필+마스크를 확인했지만 옵션별 구성이 달라 별도 기록했다.\n- 모든 후보에서 할인 표시를 관찰했다. 비행사 비교군이 없어 행사 여부와 상단 혜택 문구의 관계를 검증할 수 없다.\n- 아누아·온그리디언츠는 유명인 소구가 효능 설명과 함께 노출됐다. 이를 효과·매출의 증거로 쓰지 않는다.\n- 프리메라의2배 문구는 세럼+겔 마스크 병행 구간이다. 단품 추천에 그대로 옮기지 않도록 적용 범위를 붙였다.\n- 셀리맥스의 광고TOP.1과 실제 관찰 순위10은 다른 필드다. 이미지 광고의 순위를 현재 랭킹으로 덮어쓰지 않았다.\n\n## 본품을 맞춘 플랫폼 비교2건\n\n|비교|올리브영|무신사|관찰과 제한|\n|---|---|---|---|\n|온그리디언츠 레티날0.2%|25,000원/21%;NEW·앰버서더 행사|28,900원/10%;무뷰페·배송·첫구매쿠폰|브랜드·제품명 기준 동일 본품.전성분 완전 일치 미확인|\n|셀리맥스 레티날 부스터15ml|23,100원/23%;모공탄력;15+3ml|29,700원/1%;모공잡티세럼팩1매 증정|본품은 같고 증정품이 다름.판매 구성 전체 고정 아님|\n\n[온그리디언츠 올리브영](${products[2].product_url}) · [무신사](https://www.musinsa.com/products/7073570)\n\n[셀리맥스 올리브영](${products[3].product_url}) · [무신사](https://www.musinsa.com/products/5142164)\n\n이는 조건을 완전히 통제한 실험이 아니라 **본품을 맞춘 관찰 비교**다. 브랜드·본품을 고정해 표현 차이를 설명하는 용도이며, 가격·구성·광고 노출·플랫폼 이용자의 차이는 남아 있다. 컬리는 동일 제품 페이지를 충분히 확인하지 못해 추가하지 않았다.\n\n## 데이터 품질·활용 한계\n\n1. 순위·리뷰·평점은 성과 대리 지표이며 매출·판매량이 아니다. 공개 제품 실적은 확보하지 못해 금액·수량은 공란,상태는 미공개로 기록했다.\n2. 원본 인체적용시험 자료나 기능성 등록 원본은 확보하지 않았다. 시험조건 확인은 공개 광고의 표기 확인일 뿐,시험 타당성이나 법적 적합성 확인이 아니다.\n3. 시험조건 미확인은 표기가 없다는 뜻이 아니다. 이번에 열람한 구간에서 확인하지 못했다는 뜻이다. 하단 전체 전수 확인은 완료되지 않았다.\n4. 프리메라는 상품명25g·고시30g가 불일치하고 표시가에 ~가 있다. 옵션 확정 전 기획세트 가격으로 비교하면 안 된다. 아이오페는 고시880IU와 상세이미지 주석800IU/g가 달라 그대로 기록했다.\n5. 보유 근거가 없는 실제 제품에0/1/2를 수동 지정하지 않았다. 향후 판정 결과는 ‘공개 정보로 검토한 시스템 출력’으로 표현하고 실제 브랜드의 법 위반 확정으로 발표하지 않는다.\n6. 시장 문구는 추천 표현의 참고 자료다. 자사 효능·수치·비교 우위를 입증하는 규정/시험 근거로 검색하지 않도록 별도 데이터로 유지한다. 유명 제품의 수치나 시험조건을 자사에 전용하지 않는다.\n7. 문구 단독 효과·기여 매출·상승률을 계산하지 않는다. 본 샘플의 관찰을 문구가 잘 팔리게 했다는 인과관계로 해석할 수 없다.\n\n## 다음 확장 전 보완할 항목\n\n- 온그리디언츠·아이오페의 주름 기능성 유형 표시 확보 또는 유형이 확인된 상위 제품으로 교체.\n- 세럼/앰플 세부 랭킹을 확보하면 해당 순위로 재선정.현재 스킨케어 순위를 세럼 순위로 명명하지 않기.\n- 태그7종 제안 확인;상세 상단/하단 위치는 ‘제품 설명 구간의 전반/후반’으로 통일하고 전수 채록 범위 확정.\n- 본문 문구와 주변 주석·옵션을 함께 확인한 뒤 나머지 카테고리로 확대.현재는5개 형식 샘플에서 중단.\n`;
const confirmedIds=new Set(products.filter(p=>p.functional_type).map(p=>p.product_id));
const confirmedDistribution='주름 기능성 유형을 명시 확인한 **3개만의 발췌 분포**는 다음과 같다.\n\n|유형|사용 제품 수/3|\n|---|---:|\n'+tags.map(t=>`|${t}|${new Set(copies.filter(c=>confirmedIds.has(c.product_id)&&c['문구 유형'].includes(t)).map(c=>c.product_id)).size}/3|`).join('\n')+'\n\n';
const functionalLinks=`\n\n기능성 유형 확인 출처: [아누아 공식 제품 고시](${sources.anua}), [프리메라 공식 바운시 리프트 설명의 기능성 아이콘](${sources.primera}), [셀리맥스 공식 기능성여부 고시](${sources.celimax}). 공개 표시 확인이며, 규제기관 원본 심사자료 확보를 뜻하지 않는다.\n`;
await fs.writeFile(path.join(root,'summary.md'),summary.replace('**태그 보완 제안:**',confirmedDistribution+'**태그 보완 제안:**')+functionalLinks,'utf8');
console.log(JSON.stringify({products:products.length,copies:copies.length,comparisons:comparisons.length,judge_null:copies.every(c=>c.judge_level===null),functional_type_verified:products.filter(p=>p.functional_type).length}));
