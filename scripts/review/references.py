#!/usr/bin/env python3
"""Harvard (Cite Them Right style) references and in-text citations for the review (V14).

Sources, in order of preference:
  1. the Crossref record cached in myliteraturereviewpaper/_src/V14/crossref/<ID>.json (authors, container,
     volume, issue, pages) — fetched by fetch_crossref.py for every paper that prints a DOI, and for the few
     copies that are the author's version of a published article;
  2. MANUAL below — the details printed on the corpus copy (arXiv preprints, proceedings without a DOI);
  3. BACKGROUND below — works cited by the review that are not in the corpus (method, foundations, law,
     the supervisors' reviews).
Titles are taken as printed on the paper (papers.csv), not from Crossref.

Usage: scripts/.venv/bin/python scripts/review/references.py   -> writes _src/V14/references.json
"""
import csv, json, pathlib, re, unicodedata, collections, html

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14'
MAX_AUTHORS = 10          # more than this: first author followed by 'et al.'

# ---------------------------------------------------------------- manual records (copy in hand)
def A(*names):
    """names as 'Family, Given' strings"""
    return [tuple(x.strip() for x in n.split(',', 1)) for n in names]

MANUAL = {
 'O015': dict(authors=A('Paikens, Pēteris', 'Nesenbergs, Krišjānis'), year=2024, kind='proc',
              container='CyCon 2024: Over the Horizon — 16th International Conference on Cyber Conflict',
              editors='Kwan, C., Lindström, L., Giovannelli, D., Podiņš, K. and Štrucl, D.',
              place='Tallinn', publisher='NATO CCDCOE Publications', pages='47–62'),
 'O018': dict(authors=A('Wang, Zhe'), year=2024, kind='arxiv', arxiv='2404.16846'),
 'O025': dict(authors=A('Kazemian, Mohsen'), year=2024, kind='arxiv', arxiv='2408.03028'),
 'O032': dict(authors=A('Ruas, Inês Campos', 'Ben Dhaou, Soumaya', 'Jordanoski, Zoran'), year=2023, kind='proc',
              container='Proceedings of EGOV-CeDEM-ePart 2023, Budapest, Hungary, 4–7 September 2023',
              series='CEUR Workshop Proceedings, 3449', url='https://ceur-ws.org/Vol-3449/paper14.pdf'),
 'O065': dict(authors=A('Zhao, Zihao', 'Li, Yijiang', 'Yang, Yuchen', 'Zhang, Wenqing', 'Vasconcelos, Nuno', 'Cao, Yinzhi'),
              year=2024, kind='arxiv', arxiv='2411.02622'),
 'O066': dict(authors=A('Vepakomma, Praneeth', 'Gupta, Otkrist', 'Swedish, Tristan', 'Raskar, Ramesh'), year=2018,
              kind='arxiv', arxiv='1812.00564'),
 'O067': dict(authors=A('Li, Zhuohang', 'Yan, Chao', 'Zhang, Xinmeng', 'Gharibi, Gharib', 'Yin, Zhijun', 'Jiang, Xiaoqian',
                        'Malin, Bradley A.'), year=2023, kind='journal', container='AMIA Annual Symposium Proceedings',
              volume='2023', pages='1047–1056', url='https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10785879/'),
 'O069': dict(authors=A('Nowell, Eustace', 'Gallus, Sameera'), year=2025, kind='preprint', container='Preprints.org',
              doi='10.20944/preprints202501.0685.v1'),
 'O071': dict(authors=A('Zhang, Chaoyu', 'Li, Shaoyu'), year=2025, kind='arxiv', arxiv='2404.16847'),
 'O072': dict(authors=A('Baranski, Stanislaw'), year=2024, kind='journal', container='TASK Quarterly', volume='28',
              issue='2', doi='10.34808/tq2024/28.2/b'),
 'O075': dict(authors=A('Xu, Runhua', 'Baracaldo, Nathalie', 'Joshi, James'), year=2021, kind='arxiv', arxiv='2108.04417'),
 'O076': dict(authors=A('Zeng, Wenxuan', 'Xu, Tianshi', 'Chen, Yi', 'Zhou, Yifan', 'Zhang, Mingzhe', 'Tan, Jin',
                        'Hong, Cheng', 'Li, Meng'), year=2025, kind='arxiv', arxiv='2507.14519'),
 'O083': dict(authors=A('Shompa, Sayma Nasrin'), year=2025, kind='journal',
              container='International Journal of Ethical AI Application', pages='37–48',
              url='https://ijeaa.cultechpub.com/index.php/ijeaa'),
 'O084': dict(authors=A('Nguyen, Thanh Tam', 'Huynh, Thanh Trung', 'Ren, Zhao', 'Nguyen, Thanh Toan', 'Nguyen, Phi Le',
                        'Yin, Hongzhi', 'Nguyen, Quoc Viet Hung'), year=2024, kind='arxiv', arxiv='2404.00673'),
 'O086': dict(authors=A('Khan, Tanveer', 'Nguyen, Khoa', 'Michalas, Antonis'), year=2023, kind='arxiv', arxiv='2309.08697'),
 'O089': dict(authors=A('Mo, Fan', 'Tarkhani, Zahra', 'Haddadi, Hamed'), year=2022, kind='arxiv', arxiv='2208.10134'),
 'O090': dict(authors=A('Wang, Pengli', 'Dong, Bingyou', 'Cai, Yifeng', 'Zhang, Zheng', 'Liu, Junlin', 'Xue, Huanran',
                        'Wu, Ye', 'Zhang, Yao', 'Zhang, Ziqi'), year=2025, kind='proc',
              container='Proceedings of the 34th USENIX Security Symposium', place='Seattle, WA',
              publisher='USENIX Association', pages='279–298'),
 'O091': dict(authors=A('Qu, Wenjie', 'Sun, Yijun', 'Liu, Xuanming', 'Lu, Tao', 'Guo, Yanpei', 'Chen, Kai', 'Zhang, Jiaheng'),
              year=2025, kind='proc', container='Proceedings of the 34th USENIX Security Symposium', place='Seattle, WA',
              publisher='USENIX Association', pages='2045–2063'),
 'O093': dict(authors=A('Hao, Meng', 'Chen, Hanxiao', 'Li, Hongwei', 'Weng, Chenkai', 'Zhang, Yuan', 'Yang, Haomiao',
                        'Zhang, Tianwei'), year=2024, kind='proc',
              container='Proceedings of the 33rd USENIX Security Symposium (USENIX Security 24)', place='Philadelphia, PA',
              publisher='USENIX Association', pages='3819–3836'),
 'S013': dict(authors=A('Lavin, Ryan', 'Liu, Xuekai', 'Mohanty, Hardhik', 'Norman, Logan', 'Zaarour, Giovanni',
                        'Krishnamachari, Bhaskar'), year=2026, kind='arxiv', arxiv='2408.00243'),
 'S025': dict(authors=A('Sheybani, Nojan', 'Ahmed, Anees', 'Kinsy, Michel', 'Koushanfar, Farinaz'), year=2025,
              kind='arxiv', arxiv='2502.07063'),
 'S029': dict(authors=A('Cartmell, John', 'Williams, Alexander'), year=2026, kind='arxiv', arxiv='2605.09232'),
 'S030': dict(authors=A('Zaman, Zakia', 'Gauravaram, Praveen', 'Hassan, Mahbub', 'Jha, Sanjay', 'Hu, Wen'), year=2026,
              kind='arxiv', arxiv='2603.13570'),
 # added 29 Sep 2026 from citation searching; the corpus copy of O101 is arXiv:1912.04977v3, cited in its published version
 'O101': dict(authors=A('Kairouz, Peter', 'McMahan, H. Brendan', 'Avent, Brendan', 'Bellet, Aurélien',
    'Bennis, Mehdi', 'Bhagoji, Arjun Nitin', 'Bonawitz, Kallista'), year=2021, kind='journal',
    title='Advances and open problems in federated learning', container='Foundations and Trends in Machine Learning',
    volume='14', issue='1–2', pages='1–210', doi='10.1561/2200000083'),
 'O100': dict(authors=A('Qu, Youyang', 'Uddin, Md Palash', 'Gan, Chenquan', 'Xiang, Yong', 'Gao, Longxiang',
    'Yearwood, John'), year=2022, kind='journal', title='Blockchain-enabled federated learning: a survey',
    container='ACM Computing Surveys', volume='55', issue='4', article_number='70', pages='1–35', doi='10.1145/3524104'),
 'O096': dict(authors=A('Lycklama, Hidde', 'Burkhalter, Lukas', 'Viand, Alexander', 'Küchler, Nicolas',
    'Hithnawi, Anwar'), year=2023, kind='proc', title='RoFL: robustness of secure federated learning',
    container='2023 IEEE Symposium on Security and Privacy (SP)', place='San Francisco, CA', pages='453–476',
    doi='10.1109/SP46215.2023.10179400'),
 'O098': dict(authors=A('Roy Chowdhury, Amrita', 'Guo, Chuan', 'Jha, Somesh', 'van der Maaten, Laurens'),
    year=2022, kind='proc', title='EIFFeL: ensuring integrity for federated learning',
    container='Proceedings of the 2022 ACM SIGSAC Conference on Computer and Communications Security (CCS ’22)',
    place='Los Angeles, CA', pages='2535–2549', doi='10.1145/3548606.3560611'),
 'O099': dict(authors=A('Ghodsi, Zahra', 'Javaheripi, Mojan', 'Sheybani, Nojan', 'Zhang, Xinqiao', 'Huang, Ke',
    'Koushanfar, Farinaz'), year=2023, kind='proc', title='zPROBE: zero peek robustness checks for federated learning',
    container='2023 IEEE/CVF International Conference on Computer Vision (ICCV)', place='Paris', pages='4837–4847',
    doi='10.1109/ICCV51070.2023.00448'),
 'O097': dict(authors=A('Bell, James', 'Gascón, Adrià', 'Lepoint, Tancrède', 'Li, Baiyu', 'Meiklejohn, Sarah',
    'Raykova, Mariana', 'Yun, Cathie'), year=2023, kind='proc', title='ACORN: input validation for secure aggregation',
    container='32nd USENIX Security Symposium (USENIX Security 23)', place='Anaheim, CA', pages='4805–4822',
    url='https://www.usenix.org/conference/usenixsecurity23/presentation/bell'),
 # added 29 Sep 2026 by backward snowballing from S026 and S032; arXiv only
 'O109': dict(authors=A('Xing, Zhibo', 'Zhang, Zijian', 'Li, Meng', 'Liu, Jiamou', 'Zhu, Liehuang', 'Russello, Giovanni',
              'Asghar, Muhammad Rizwan'), year=2023, kind='arxiv', arxiv='2304.05590'),
}

# Journal details missing from an early-access Crossref record, as printed on the corpus copy
PATCH = {
 'O104': dict(container='2025 IEEE/IFIP Network Operations and Management Symposium (NOMS)', pages='1–9'),
 'O051': dict(volume='33', issue='11', pages='2675–2686', year=2022),
 'O021': dict(year=2022),   # ACM TOSN 18(4), issue dated November 2022 (article published March 2023)
}

# Author names that Crossref splits wrongly (double surnames, name suffixes, initials as family names)
NAME_FIX = {
 'S009': A('Martínez Beltrán, Enrique Tomás', 'Quiles Pérez, Mario', 'Sánchez Sánchez, Pedro Miguel', 'López Bernal, Sergio',
           'Bovet, Gérôme', 'Gil Pérez, Manuel', 'Martínez Pérez, Gregorio', 'Huertas Celdrán, Alberto'),
 'S018': {0: ('Sameera', 'K. M.'), 4: ('Rafidha Rehiman', 'K. A.'), 5: ('Vinod', 'P.')},
 'S004': {'Vincent Poor': ('Poor', 'H. Vincent')},
 'S028': {'Vincent Poor': ('Poor', 'H. Vincent')},
 'S031': {'Rodríguez': ('Oropeza Rodríguez', 'José Luis')},
 'O059': {'Winnie Owoko': ('Owoko', 'Winnie')},
 'O064': {'Galende': ('Arroyo Galende', 'Borja')},
 'O054': {'Filho': ('Poncinelli Filho', 'Carlos')},
 'O016': {'Neto': ('Pinto Neto', 'Euclides Carlos')},
}

def fix_names(pid, authors):
    fx = NAME_FIX.get(pid)
    if not fx:
        return authors
    if isinstance(fx, list):
        return fx
    out = list(authors)
    for k, v in fx.items():
        if isinstance(k, int):
            out[k] = v
        else:
            out = [v if a[0] == k else a for a in out]
    return out

# ---------------------------------------------------------------- works cited that are not in the corpus
BACKGROUND = {
 'kitchenham2007': dict(authors=A('Kitchenham, Barbara', 'Charters, Stuart'), year=2007, kind='report',
    title='Guidelines for performing systematic literature reviews in software engineering',
    series='EBSE Technical Report EBSE-2007-01', publisher='Keele University and Durham University', place='Keele'),
 'page2021': dict(authors=A('Page, Matthew J.', 'McKenzie, Joanne E.', 'Bossuyt, Patrick M.', 'Boutron, Isabelle',
    'Hoffmann, Tammy C.', 'Mulrow, Cynthia D.', 'Shamseer, Larissa', 'Tetzlaff, Jennifer M.', 'Akl, Elie A.',
    'Brennan, Sue E.', 'Chou, Roger'), year=2021, kind='journal',
    title='The PRISMA 2020 statement: an updated guideline for reporting systematic reviews', container='BMJ',
    volume='372', pages='n71', doi='10.1136/bmj.n71'),
 'wohlin2014': dict(authors=A('Wohlin, Claes'), year=2014, kind='proc',
    title='Guidelines for snowballing in systematic literature studies and a replication in software engineering',
    container='Proceedings of the 18th International Conference on Evaluation and Assessment in Software Engineering (EASE ’14)',
    place='New York', publisher='ACM', pages='1–10', doi='10.1145/2601248.2601268'),
 'braun2006': dict(authors=A('Braun, Virginia', 'Clarke, Victoria'), year=2006, kind='journal',
    title='Using thematic analysis in psychology', container='Qualitative Research in Psychology', volume='3', issue='2',
    pages='77–101', doi='10.1191/1478088706qp063oa'),
 'cruzes2011': dict(authors=A('Cruzes, Daniela S.', 'Dybå, Tore'), year=2011, kind='proc',
    title='Recommended steps for thematic synthesis in software engineering',
    container='2011 International Symposium on Empirical Software Engineering and Measurement', place='Banff',
    publisher='IEEE', pages='275–284', doi='10.1109/ESEM.2011.36'),
 'zhang2011': dict(authors=A('Zhang, He', 'Babar, Muhammad Ali', 'Tell, Paolo'), year=2011, kind='journal',
    title='Identifying relevant studies in software engineering', container='Information and Software Technology',
    volume='53', issue='6', pages='625–637', doi='10.1016/j.infsof.2010.12.010'),
 'wieringa2006': dict(authors=A('Wieringa, Roel', 'Maiden, Neil', 'Mead, Nancy', 'Rolland, Colette'), year=2006,
    kind='journal', title='Requirements engineering paper classification and evaluation criteria: a proposal and a discussion',
    container='Requirements Engineering', volume='11', issue='1', pages='102–107', doi='10.1007/s00766-005-0021-6'),
 'mcmahan2017': dict(authors=A('McMahan, Brendan', 'Moore, Eider', 'Ramage, Daniel', 'Hampson, Seth',
    'Agüera y Arcas, Blaise'), year=2017, kind='proc',
    title='Communication-efficient learning of deep networks from decentralized data',
    container='Proceedings of the 20th International Conference on Artificial Intelligence and Statistics (AISTATS)',
    series='Proceedings of Machine Learning Research, 54', publisher='PMLR', pages='1273–1282'),
 'nakamoto2008': dict(authors=A('Nakamoto, Satoshi'), year=2008, kind='web',
    title='Bitcoin: a peer-to-peer electronic cash system', url='https://bitcoin.org/bitcoin.pdf'),
 'dwork2006': dict(authors=A('Dwork, Cynthia'), year=2006, kind='proc', title='Differential privacy',
    container='Automata, Languages and Programming: 33rd International Colloquium (ICALP 2006)',
    series='Lecture Notes in Computer Science, 4052', place='Berlin', publisher='Springer', pages='1–12',
    doi='10.1007/11787006_1'),
 'gentry2009': dict(authors=A('Gentry, Craig'), year=2009, kind='proc',
    title='Fully homomorphic encryption using ideal lattices',
    container='Proceedings of the 41st Annual ACM Symposium on Theory of Computing (STOC ’09)', place='New York',
    publisher='ACM', pages='169–178', doi='10.1145/1536414.1536440'),
 'yao1982': dict(authors=A('Yao, Andrew C.'), year=1982, kind='proc', title='Protocols for secure computations',
    container='23rd Annual Symposium on Foundations of Computer Science (SFCS 1982)', publisher='IEEE',
    pages='160–164', doi='10.1109/SFCS.1982.38'),
 'shamir1979': dict(authors=A('Shamir, Adi'), year=1979, kind='journal', title='How to share a secret',
    container='Communications of the ACM', volume='22', issue='11', pages='612–613', doi='10.1145/359168.359176'),
 'goldwasser1989': dict(authors=A('Goldwasser, Shafi', 'Micali, Silvio', 'Rackoff, Charles'), year=1989, kind='journal',
    title='The knowledge complexity of interactive proof systems', container='SIAM Journal on Computing', volume='18',
    issue='1', pages='186–208', doi='10.1137/0218012'),
 'costan2016': dict(authors=A('Costan, Victor', 'Devadas, Srinivas'), year=2016, kind='report', title='Intel SGX explained',
    series='Cryptology ePrint Archive, Paper 2016/086', url='https://eprint.iacr.org/2016/086'),
 'gdpr2016': dict(authors=[('European Parliament and Council of the European Union', '')], year=2016, kind='law',
    title='Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 on the protection of '
          'natural persons with regard to the processing of personal data and on the free movement of such data '
          '(General Data Protection Regulation)',
    container='Official Journal of the European Union', series='L 119, 4 May 2016', pages='1–88'),
 'edpb2026': dict(authors=[('European Data Protection Board', '')], year=2026, kind='report',
    title='Guidelines 02/2025 on processing of personal data through blockchain technologies',
    series='Version 2.0, adopted on 7 July 2026', place='Brussels', publisher='EDPB'),
 'hevner2004': dict(authors=A('Hevner, Alan R.', 'March, Salvatore T.', 'Park, Jinsoo', 'Ram, Sudha'), year=2004,
    kind='journal', title='Design science in information systems research', container='MIS Quarterly', volume='28',
    issue='1', pages='75–106', doi='10.2307/25148625'),
 'peffers2007': dict(authors=A('Peffers, Ken', 'Tuunanen, Tuure', 'Rothenberger, Marcus A.', 'Chatterjee, Samir'),
    year=2007, kind='journal', title='A design science research methodology for information systems research',
    container='Journal of Management Information Systems', volume='24', issue='3', pages='45–77',
    doi='10.2753/MIS0742-1222240302'),
 'kavianpour2019': dict(authors=A('Kavianpour, Sanaz', 'Shanmugam, Bharanidharan', 'Azam, Sami', 'Zamani, Mazdak',
    'Narayana Samy, Ganthan', 'De Boer, Friso'), year=2019, kind='journal',
    title='A systematic literature review of authentication in Internet of Things for heterogeneous devices',
    container='Journal of Computer Networks and Communications', volume='2019', pages='5747136',
    article=True, doi='10.1155/2019/5747136'),
 'salim2020': dict(authors=A('Salim, Mikail Mohammed', 'Rathore, Shailendra', 'Park, Jong Hyuk'), year=2020,
    kind='journal', title='Distributed denial of service attacks and its defenses in IoT: a survey',
    container='The Journal of Supercomputing', volume='76', issue='7', pages='5320–5363',
    doi='10.1007/s11227-019-02945-z'),
 'kim2018': dict(authors=A('Kim, Nam Yong', 'Rathore, Shailendra', 'Ryu, Jung Hyun', 'Park, Jin Ho', 'Park, Jong Hyuk'),
    year=2018, kind='journal', title='A survey on cyber physical system security for IoT: issues, challenges, threats, solutions',
    container='Journal of Information Processing Systems', volume='14', issue='6', pages='1361–1384',
    doi='10.3745/JIPS.03.0105'),
 'petersen2015': dict(authors=A('Petersen, Kai', 'Vakkalanka, Sairam', 'Kuzniarz, Ludwik'), year=2015, kind='journal',
    title='Guidelines for conducting systematic mapping studies in software engineering: an update',
    container='Information and Software Technology', volume='64', pages='1–18', doi='10.1016/j.infsof.2015.03.007'),
 'ampatzoglou2020': dict(authors=A('Ampatzoglou, Apostolos', 'Bibi, Stamatia', 'Avgeriou, Paris',
    'Chatzigeorgiou, Alexander'), year=2020, kind='chapter',
    title='Guidelines for managing threats to validity of secondary studies in software engineering',
    container='Contemporary Empirical Methods in Software Engineering', editors='M. Felderer and G. H. Travassos',
    place='Cham, Switzerland', publisher='Springer', pages='415–441', doi='10.1007/978-3-030-32489-6_15'),
 'heenan2026': dict(authors=A('Heenan, Ross', 'Ferguson, Ian', 'Al-Jobouri, Laith'), year=2026, kind='proc',
    title='An analysis of malware threats facing the IoT: a taxonomy of IoT malware',
    container='CROSS-SEC 2026: The First International Conference on Cross-Domain Security in Distributed, Intelligent '
              'and Critical Systems', publisher='IARIA', pages='112–127'),
}

# ---------------------------------------------------------------- helpers
def initials(given):
    parts = []
    for tok in re.split(r'\s+', given.strip()):
        if not tok:
            continue
        sub = [s for s in tok.split('-') if s]
        parts.append('-'.join(s[0].upper() + '.' for s in sub if s[0].isalpha()))
    return ''.join(parts)

def author_str(a):
    fam, giv = a
    return f"{fam}, {initials(giv)}" if giv else fam

def authors_ref(authors):
    if len(authors) > MAX_AUTHORS:
        return author_str(authors[0]) + ' et al.'
    names = [author_str(a) for a in authors]
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]

def authors_cite(authors):
    fam = [a[0] for a in authors]
    if len(fam) == 1:
        return fam[0]
    if len(fam) == 2:
        return f"{fam[0]} and {fam[1]}"
    if len(fam) == 3:
        return f"{fam[0]}, {fam[1]} and {fam[2]}"
    return f"{fam[0]} et al."

def dash(p):
    return (p or '').replace('--', '–').replace('-', '–')

def from_crossref(m):
    auth = []
    for a in m.get('author', []):
        fam = a.get('family') or a.get('name') or ''
        auth.append((fam.strip(), (a.get('given') or '').strip()))
    kind = 'journal' if m.get('type') == 'journal-article' else 'proc' if m.get('type') == 'proceedings-article' else 'other'
    rec = dict(authors=auth, kind=kind, container=(m.get('container-title') or [''])[0], volume=m.get('volume') or '',
               issue=m.get('issue') or '', pages=dash(m.get('page') or ''), doi=m.get('DOI', ''),
               article_number=m.get('article-number') or '', publisher=m.get('publisher') or '')
    yp = (m.get('published-print') or m.get('journal-issue', {}).get('published-print') or m.get('issued') or {})
    rec['year_crossref'] = (yp.get('date-parts') or [[None]])[0][0]
    return rec

def fmt_ref(r):
    """Return the reference as a list of (text, italic) runs."""
    runs = [(f"{authors_ref(r['authors'])} ({r['year']}{r.get('suffix','')}) ", False)]
    k = r['kind']
    title = r['title'].strip().rstrip('.')
    tail = []
    if k in ('journal', 'other') and r.get('container'):
        runs += [(f"‘{title}’, ", False), (r['container'], True)]
        v = r.get('volume', '')
        if v:
            tail.append(f"{v}({r['issue']})" if r.get('issue') else v)
        p = r.get('pages', '')
        art = r.get('article_number', '')
        if art:
            tail.append(f"Article {art}")
        elif p and '–' not in p:
            # a single locator is an article number (e.g. 108621) or an e-locator (BMJ n71)
            tail.append(p if not p.isdigit() else f"Article {p}")
        elif p and not (art and p.startswith('1–')):
            tail.append(f"pp. {p}")
    elif k == 'proc':
        runs += [(f"‘{title}’, in ", False)]
        if r.get('editors'):
            runs += [(f"{r['editors']} (eds) ", False)]
        runs += [(r.get('container', ''), True)]
        if r.get('series'):
            tail.append(r['series'])
        pp = []
        if r.get('place') and r.get('publisher'):
            pp.append(f"{r['place']}: {r['publisher']}")
        elif r.get('publisher'):
            pp.append(r['publisher'])
        tail += pp
        if r.get('pages'):
            tail.append(f"pp. {r['pages']}")
    elif k == 'arxiv':
        runs += [(f"‘{title}’, ", False), ('arXiv preprint', True)]
        tail.append(f"arXiv:{r['arxiv']}")
    elif k == 'preprint':
        runs += [(f"‘{title}’, ", False), (r.get('container', 'Preprint'), True)]
        tail.append('preprint (not peer reviewed)')
    elif k == 'report':
        runs += [(title, True)]
        if r.get('series'):
            tail.append(r['series'])
        if r.get('place') and r.get('publisher'):
            tail.append(f"{r['place']}: {r['publisher']}")
        elif r.get('publisher'):
            tail.append(r['publisher'])
    elif k == 'law':
        runs += [(title, True)]
        tail.append(f"{r['container']}, {r['series']}")
        if r.get('pages'):
            tail.append(f"pp. {r['pages']}")
    elif k == 'web':
        runs += [(title, True)]
    else:
        runs += [(f"‘{title}’", False)]
    text_tail = (', ' + ', '.join(tail)) if tail else ''
    link = ''
    if r.get('doi'):
        link = f" Available at: https://doi.org/{r['doi']}"
    elif r.get('arxiv'):
        link = f" Available at: https://arxiv.org/abs/{r['arxiv']}"
    elif r.get('url'):
        link = f" Available at: {r['url']}"
    runs.append((text_tail + '.' + link + ('.' if link else ''), False))
    # tidy
    out = []
    for t, it in runs:
        t = t.replace(' ,', ',').replace('..', '.')
        out.append((t, it))
    return out


# ---------------------------------------------------------------- IEEE (numbered) style, used from V15
def initials_ieee(given):
    parts = []
    for tok in re.split(r'\s+', given.strip()):
        if not tok:
            continue
        sub = [x for x in tok.split('-') if x]
        parts.append('-'.join(x[0].upper() + '.' for x in sub if x[0].isalpha()))
    return ' '.join(parts)


def author_ieee(a):
    fam, giv = a
    return f"{initials_ieee(giv)} {fam}".strip() if giv else fam


def authors_ieee(authors):
    if len(authors) > 6:
        return author_ieee(authors[0]) + ' et al.'
    names = [author_ieee(a) for a in authors]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ', '.join(names[:-1]) + ', and ' + names[-1]


def narrative_ieee(authors):
    fam = [a[0] for a in authors]
    if len(fam) == 1:
        return fam[0]
    if len(fam) == 2:
        return f"{fam[0]} and {fam[1]}"
    return f"{fam[0]} et al."


def fmt_ieee(r):
    """Return the IEEE-style reference (without its number) as a list of (text, italic) runs."""
    au = authors_ieee(r['authors'])
    title = r['title'].strip().rstrip('.')
    k = r['kind']
    runs = []
    tail = []
    if k in ('journal', 'other') and r.get('container'):
        runs += [(f"{au}, “{title},” ", False), (r['container'], True)]
        if r.get('volume'):
            tail.append(f"vol. {r['volume']}")
        if r.get('issue'):
            tail.append(f"no. {r['issue']}")
        p = r.get('pages', '')
        art = r.get('article_number', '')
        if art:
            tail.append(f"Art. no. {art}")
        elif p and '–' not in p:
            tail.append(f"Art. no. {p}" if p.isdigit() else p)
        elif p:
            tail.append(f"pp. {p}")
        tail.append(str(r['year']))
    elif k == 'proc':
        runs += [(f"{au}, “{title},” in ", False), (r.get('container', ''), True)]
        if r.get('series'):
            tail.append(r['series'])
        if r.get('place'):
            tail.append(r['place'])
        tail.append(str(r['year']))
        if r.get('pages'):
            tail.append(f"pp. {r['pages']}")
    elif k == 'arxiv':
        runs += [(f"{au}, “{title},” ", False), ('arXiv preprint', True)]
        tail += [f"arXiv:{r['arxiv']}", str(r['year'])]
    elif k == 'preprint':
        runs += [(f"{au}, “{title},” ", False), (r.get('container', 'Preprint'), True)]
        tail += ['preprint', str(r['year'])]
    elif k == 'report':
        runs += [(f"{au}, “{title},” {r.get('publisher') or ''}", False)]
        for x in (r.get('place'), r.get('series')):
            if x:
                tail.append(x)
        tail.append(str(r['year']))
    elif k == 'law':
        runs += [(f"{au}, “{title},” ", False), (r['container'], True)]
        vol, _, date = r['series'].partition(', ')
        tail += [f"vol. {vol}", f"pp. {r['pages']}", date or str(r['year'])]
    elif k == 'chapter':
        runs += [(f"{au}, “{title},” in ", False), (r['container'], True),
                 (f", {r['editors']}, Eds. {r['place']}: {r['publisher']}", False)]
        tail += [str(r['year']), f"pp. {r['pages']}"]
    elif k == 'web':
        runs += [(f"{au}, “{title},” {r['year']}. [Online]. Available: {r['url']}", False)]
        return runs
    else:
        runs += [(f"{au}, “{title},” {r['year']}", False)]
    text_tail = (', ' + ', '.join(tail)) if tail else ''
    link = ''
    if r.get('doi'):
        link = f", doi: {r['doi']}"
    elif r.get('url') and k != 'web':
        link = f". [Online]. Available: {r['url']}"
    runs.append((text_tail + link + ('.' if not link.startswith('. [Online]') else ''), False))
    return runs


def sort_key(r):
    fam = [unicodedata.normalize('NFKD', a[0]).encode('ascii', 'ignore').decode().lower() for a in r['authors']]
    first = fam[0] if fam else ''
    n = len(fam)
    group = 0 if n == 1 else 1 if n == 2 else 2 if n == 3 else 3   # single, pair, three, et al. (same first author)
    return (first, group, fam[1:] if n <= 3 else [], r['year'], r.get('suffix', ''), r['title'].lower())

def build():
    papers = {p['id']: p for p in csv.DictReader(open(ROOT / 'corpus' / '_extraction' / 'papers.csv', encoding='utf-8'))}
    excluded = set(json.loads((SRC / 'screening.json').read_text())['excluded']) if (SRC / 'screening.json').exists() else set()
    refs = {}
    for pid, p in papers.items():
        if pid in excluded:
            continue
        f = SRC / 'crossref' / f'{pid}.json'
        if pid in MANUAL:
            r = dict(MANUAL[pid])
        elif f.exists():
            m = json.loads(f.read_text())
            r = from_crossref(m)
            # the corpus year, except where the copy was replaced by its published version
            r['year'] = int(r['year_crossref']) if m.get('_note', '').startswith('DOI supplied') and 'another article' not in m['_note'] else int(p['year'])
        else:
            raise SystemExit(f'no reference source for {pid}')
        r.update(PATCH.get(pid, {}))
        r['authors'] = fix_names(pid, r['authors'])
        r['container'] = html.unescape(r.get('container', ''))
        r['title'] = p['title']
        r['id'] = pid
        refs[pid] = r
    for key, b in BACKGROUND.items():
        r = dict(b)
        r['id'] = key
        refs[key] = r
    # a/b suffixes where the in-text citation would be identical
    groups = collections.defaultdict(list)
    for r in refs.values():
        groups[(authors_cite(r['authors']), r['year'])].append(r)
    for (_, _), rs in groups.items():
        if len(rs) > 1:
            rs.sort(key=lambda r: r['title'].lower())
            for i, r in enumerate(rs):
                r['suffix'] = 'abcdefghij'[i]
    for r in refs.values():
        r['cite'] = f"{authors_cite(r['authors'])}, {r['year']}{r.get('suffix','')}"
        r['cite_narrative'] = f"{authors_cite(r['authors'])} ({r['year']}{r.get('suffix','')})"
        r['runs'] = fmt_ref(r)
        r['text'] = ''.join(t for t, _ in r['runs'])
        r['runs_ieee'] = fmt_ieee(r)
        r['text_ieee'] = ''.join(t for t, _ in r['runs_ieee'])
        r['narrative_ieee'] = narrative_ieee(r['authors'])
    order = sorted(refs.values(), key=sort_key)
    out = {'order': [r['id'] for r in order], 'refs': refs}
    (SRC / 'references.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out

if __name__ == '__main__':
    out = build()
    print(len(out['order']), 'references')
    for rid in out['order']:
        print(out['refs'][rid]['text'])
