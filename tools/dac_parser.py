# -*- coding: utf-8 -*-
import mechanize
import urllib
import requests
import re
import sys

################################################################################
# Constantes
################################################################################

### URLs
MAIN_URL = 'http://www.daconline.unicamp.br/altmatr/menupublico.do'
REQUEST_URL = 'http://www.daconline.unicamp.br/altmatr/conspub_matriculadospordisciplinaturma.do?org.apache.struts.taglib.html.TOKEN=%s&txtDisciplina=%s&txtTurma=%s&cboSubG=%s&cboSubP=%s&cboAno=%s&btnAcao=Continuar'
CATALOGO = "http://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2016/coordenadorias/"

### Regex patterns
TOKEN_PATTERN = 'var token = "((?P<token>[0-9a-f]{32,32}))";'
DISCIPLINE_PATTERN = 'Disciplina:</span>&nbsp;&nbsp;(?P<disciplina>[A-Za-z][A-Za-z ][0-9]{3}) (?P<turma>[A-Za-z0-9]) &nbsp;&nbsp; -&nbsp;&nbsp; (?P<materia>.+)</td>'
PROFESSOR_PATTERN = 'Docente:</span>&nbsp;&nbsp;(?P<professor>.+)</td>'
RA_PATTERN = '<td height="18" bgcolor="white" align="center" class="corpo" width="80">([0-9]+)</td>'
NAME_PATTERN = '<td height="18" bgcolor="white" width="270" align="left" class="corpo">&nbsp;&nbsp;&nbsp;&nbsp;(.+)</td>'

COURSE_PATTERN = '<div class="ancora"><a name="([A-Z][A-Z][0-9]{3})">[A-Z][A-Z][0-9]{3} - (.*)</a> </div>[^\Z]*? C:([0-9]{3}) [^\Z]*?<strong>Ementa: </strong>(.*)<br />'

################################################################################
# Funções
################################################################################

def get_students(info):
    """
    Busca lista de alunos e informações de turmas de uma determinada disciplina.
    Recebe como parâmetro um dicionário da seguinte forma:
    info = {
        'course': 'MC868',   # Código da disciplina
        'classes': 'A',   # or 'AB', 'XYWZ'
        'year': '2013',   # Ano do oferecimento
        'semester': '2',
        'type': 'undergrad'   # or 'grad'
    }
    Retorna uma lista com a seguinte tupla para cada turma:
        (
            'MC868',   # Código da disciplina
            'A',   # Identificador da turma
            'Linguagens Formais e Autômatos',   # Nome da disciplina
            'Arnaldo Vieira Moura',   # Nome do professor responsável
            [ lista de tuplas (ra, nome) para cada aluno matriculado ]
        )
    """

    # Recebe as informações da disciplina
    course = info["course"]
    classes = info["classes"]
    year = info["year"]
    if info["type"] == "undergrad":
        undergrad = info["semester"]
        grad = "0"
    elif info["type"] == "grad":
        grad = "2" + info["semester"]
        undergrad = "0"
    else:
        sys.stderr.write('dac_parser: Tipo %s Inválido.\n' % (info['type']))
        return None

    # Abre a página de consultas da DAC
    mech = mechanize.Browser()
    f = mech.open(MAIN_URL)
    site = f.read()

    # Procura pelo token da DAC
    token_pattern = re.compile(TOKEN_PATTERN)
    matches = re.search(token_pattern, site)
    if matches == None:
        sys.stderr.write("dac_parser: Não foi possível acessar o site da DAC.\n")
        sys.exit(1)
    token = matches.group("token")

    # Inicializa lista de turmas
    result = []

    # Percorre a lista com as turmas pegando os dados de seus alunos
    for cls in classes:
        # URL para onde são enviados os requerimentos
        url = REQUEST_URL % (token, course, cls,undergrad, grad, year)

        # Abre a página que contém as informações dos alunos
        f = mech.open(url)
        site = f.read()

        # Obtem informações através de regex
        # Nome do professor
        matches = re.search(PROFESSOR_PATTERN, site)
        if matches == None:
            # Turma inválida (não há docente responsável)
            sys.stderr.write("dac_parser: Turma %s Inválida.\n" % (course+cls))
            continue
        prof = matches.group("professor").strip()

        # Nome da disciplina
        matches = re.search(DISCIPLINE_PATTERN, site)
        if matches == None:
            # Turma inválida (não encontrou nome da disciplina)
            sys.stderr.write("dac_parser: Turma %s Inválida.\n" % (course+cls))
            continue
        disc = matches.group("disciplina").strip()
        class_id = matches.group("turma").strip()
        disc_name = matches.group("materia").strip()

        # Lista de matrículados
        ra_list = re.findall(RA_PATTERN, site)
        names = re.findall(NAME_PATTERN, site)

        # Turma vazia, descarta-a
        if len(names) == 0:
            sys.stderr.write("dac_parser: Turma %s Inválida.\n" % (course+cls))
            continue

        # Erro de parsing
        if len(names) != len(ra_list):
            sys.stderr.write("dac_parser: Problema lendo alunos da Turma %s.\n" % (course+cls))
            continue

        # Gera dicionário onde chave é letra da turma e itens uma lista de
        # (ra,nome) de cada aluno matriculado na turma
        students = []
        for i in range(len(ra_list)):
            students.append( (ra_list[i], (names[i]).strip()) )

        result.append( (disc, class_id, disc_name, prof, students) )

    return result

def get_courses():
    " Retorna uma lista de tuplas (código,nome) de todas as disciplinas "

    courses = []
    i = 1;

    regex = re.compile(COURSE_PATTERN)
    while(True):
        page = requests.get(CATALOGO + str(i).zfill(4) + '/' + str(i).zfill(4) + '.html');

        if(page.status_code == 404):
            break

        matches = regex.finditer(page.text);
        for match in matches:
            course_id = match.group(1)
            course_name =  match.group(2)
            credits = match.group(3)
            description = match.group(4)
            courses.append((course_id,course_name,credits,description))

        i += 1

    return courses

def get_offerings(course,semester):
    """
    Retorna uma lista de todas os oferecimentos da disciplina dada
    disciplina é o código da disciplina (ex EE400). semestre é 1 ou 2
    O retorno e uma lista de tuplas
    (Turma, Professor), ambos são string
    """
    BASE_URL = "http://www.dac.unicamp.br/sistemas/horarios/grad/"
    url = BASE_URL + "G" + str(semester) + "S0/" + course + ".htm"
    page = requests.get(url)
    offerings = []

    if(page.status_code == 404):
        return None

    regex = re.compile(
            """<b>Turma:</b>(?:</font>| )&nbsp;&nbsp;(.+)[^\Z]*?<br>(.+) \(Respons&aacute;vel\)"""
        )

    matches = regex.finditer(page.text)

    for match in matches:
        turma = match.group(1).strip()
        professor = match.group(2)
        offerings.append((turma,professor))

    return offerings






