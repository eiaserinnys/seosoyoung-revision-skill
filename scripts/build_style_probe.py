#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""문체 비교에 사용할 기준 문장과 초안 문장을 만든다."""

import argparse
import html
import io
import json
import os
import random
import re
import sys


SKIP_PREFIX = ('|', '#', '!', '>', '<', '[', '```')
SPLIT = re.compile(
    r'(?<=다\.)\s+|(?<=요\.)\s+|(?<=까\.)\s+|(?<=가\.)\s+'
    r'|(?<=까\?)\s+|(?<=가\?)\s+|(?<=다!)\s+|(?<=요!)\s+'
    r'|(?<=죠\.)\s+|(?<=네\.)\s+'
)
POLITE_RE = re.compile(r'(?:니다|니까|옵니다|소서|지요|군요|어요|아요|해요|네요|죠)[.!?]$')
POLITE_EXCEPT = ('아니다.', '아니다!', '아니다?')
SENT_END = ('다.', '까.', '가.', '요.', '까?', '가?', '다!', '요!', '죠.', '네.')
NUM_MARKER = re.compile(r'^\d+\.\s*')
BULLET_MARKER = re.compile(r'^[-*]\s+')
DRAFT_BULLET_MARKER = re.compile(r'^[-*+]\s+')
DRAFT_SKIP_PREFIX = ('|', '#', '!', '>', '<', '```')
REFERENCE_DEFINITION = re.compile(r'^\[[^\]]+\]:(?:\s|$)')

HTML_STRIP_BLOCKS = re.compile(
    r'<(?:script|style|svg|head|noscript|code|pre)\b[^>]*>[\s\S]*?</(?:script|style|svg|head|noscript|code|pre)>'
    r'|<!--[\s\S]*?-->',
    re.IGNORECASE,
)
HTML_BLOCK_END = re.compile(
    r'</(?:p|div|li|h[1-6]|tr|blockquote|section|article|dd|dt|figcaption|header|footer|aside)>'
    r'|<br\s*/?>',
    re.IGNORECASE,
)
HTML_TAG = re.compile(r'<[^>]+>')
FENCE_LINE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
HTML_CODE_BLOCKS = re.compile(
    r'<pre\b[^>]*>[\s\S]*?</pre\s*>|<code\b[^>]*>[\s\S]*?</code\s*>',
    re.IGNORECASE,
)
MULTI_SPACE = re.compile(r'[ \t]+')
SUPPORTED_EXTENSIONS = ('.md', '.txt', '.html', '.htm')
SKIP_DIRECTORIES = {'.git', '.venv', 'node_modules', '__pycache__'}
MIN_REFERENCE_SENTENCES = 20

DEFAULT_POLITE_CORPUS = (
    '초안의 문장을 살필 때에는 글의 목적과 읽는 사람을 먼저 확인해야 합니다.',
    '문단마다 중심 생각이 하나씩 드러나면 독자는 글의 흐름을 따라가기 쉽습니다.',
    '같은 뜻을 여러 번 설명하는 문장은 핵심 정보만 남겨 간결하게 다듬을 수 있습니다.',
    '기술 문서에서는 생소한 용어를 처음 쓸 때 짧은 뜻풀이를 함께 두는 편이 좋습니다.',
    '예시는 규칙을 반복해서 설명하기보다 실제로 어떻게 쓰이는지 보여 주어야 합니다.',
    '문장을 나눌 때에는 종결 표현과 문서의 형식을 함께 살펴야 정확도를 높일 수 있습니다.',
    '목록과 표의 문구는 문장으로 이어지는 산문과 구별해 기준 자료에서 제외해야 합니다.',
    '비슷한 문장이라도 독자에게 새로운 정보를 더하지 않으면 하나로 정리하는 편이 낫습니다.',
    '수정한 문장은 원래 글의 주장과 근거를 유지하는지 다시 읽으며 확인해야 합니다.',
    '낯선 약어를 한꺼번에 늘어놓으면 문장의 의미를 파악하는 데 시간이 더 걸립니다.',
    '긴 문장에는 서로 다른 주장이 함께 들어 있는지 살펴 두 문장으로 나눌 수 있습니다.',
    '문단의 첫 문장이 주제를 알리고 뒤의 문장들이 근거를 보태면 구조가 선명해집니다.',
    '독자가 바로 알 수 있는 내용은 별도의 안내 문장으로 되풀이하지 않아도 됩니다.',
    '표현을 고칠 때에는 화자의 말투와 글 전체의 높임 정도를 일관되게 맞추어야 합니다.',
    '맞춤법과 띄어쓰기를 확인한 뒤에는 소리 내어 읽으며 어색한 호흡을 찾아야 합니다.',
    '문서의 제목은 본문을 요약하고 검색할 때 내용을 짐작할 수 있도록 지어야 합니다.',
    '기준 문장은 서로 다른 주제를 다루어도 문체의 공통된 특징을 담고 있어야 합니다.',
    '자료를 모을 때에는 초안과 같은 문체의 문장만 비교군에 포함하는 것이 알맞습니다.',
    '문체를 판정하는 도구는 글쓴이의 개성을 단정하지 않고 검토할 후보를 제시해야 합니다.',
    '검토자는 수치만 따르기보다 문장이 실제 맥락에서 자연스럽게 읽히는지 판단해야 합니다.',
    '각 문단의 마지막 문장은 다음 문단과 이어지는 관계를 분명하게 만들어야 합니다.',
    '문장을 짧게 줄이더라도 책임 주체와 필요한 조건은 빠뜨리지 않아야 합니다.',
    '자동화 결과에는 사용한 기준과 출력 파일의 위치를 함께 적어 다시 확인하기 쉽게 합니다.',
    '문장 표본의 개수가 부족하면 결과를 확정하지 말고 더 많은 자료를 모아야 합니다.',
    '초안을 여러 차례 읽을 때에는 한 번에 한 가지 기준에 집중하는 것이 효과적입니다.',
)

DEFAULT_PLAIN_CORPUS = (
    '초안의 문장을 살필 때는 글의 목적과 읽는 사람을 먼저 확인해야 한다.',
    '문단마다 중심 생각이 하나씩 드러나면 독자는 글의 흐름을 따라가기 쉽다.',
    '같은 뜻을 여러 번 설명하는 문장은 핵심 정보만 남겨 간결하게 다듬을 수 있다.',
    '기술 문서에서는 생소한 용어를 처음 쓸 때 짧은 뜻풀이를 함께 두는 편이 좋다.',
    '예시는 규칙을 반복해서 설명하기보다 실제로 어떻게 쓰이는지 보여 줘야 한다.',
    '문장을 나눌 때는 종결 표현과 문서의 형식을 함께 살펴야 정확도를 높일 수 있다.',
    '목록과 표의 문구는 문장으로 이어지는 산문과 구별해 기준 자료에서 제외해야 한다.',
    '비슷한 문장이라도 독자에게 새로운 정보를 더하지 않으면 하나로 정리하는 편이 낫다.',
    '수정한 문장은 원래 글의 주장과 근거를 유지하는지 다시 읽으며 확인해야 한다.',
    '낯선 약어를 한꺼번에 늘어놓으면 문장의 의미를 파악하는 데 시간이 더 걸린다.',
    '긴 문장에는 서로 다른 주장이 함께 들어 있는지 살펴 두 문장으로 나눌 수 있다.',
    '문단의 첫 문장이 주제를 알리고 뒤의 문장들이 근거를 보태면 구조가 선명해진다.',
    '독자가 바로 알 수 있는 내용은 별도의 안내 문장으로 되풀이하지 않아도 된다.',
    '표현을 고칠 때는 화자의 말투와 글 전체의 높임 정도를 일관되게 맞춰야 한다.',
    '맞춤법과 띄어쓰기를 확인한 뒤에는 소리 내어 읽으며 어색한 호흡을 찾아야 한다.',
    '문서의 제목은 본문을 요약하고 검색할 때 내용을 짐작할 수 있도록 지어야 한다.',
    '기준 문장은 서로 다른 주제를 다루어도 문체의 공통된 특징을 담고 있어야 한다.',
    '자료를 모을 때는 초안과 같은 문체의 문장만 비교군에 포함하는 것이 알맞다.',
    '문체를 판정하는 도구는 글쓴이의 개성을 단정하지 않고 검토할 후보를 제시해야 한다.',
    '검토자는 수치만 따르기보다 문장이 실제 맥락에서 자연스럽게 읽히는지 판단해야 한다.',
    '각 문단의 마지막 문장은 다음 문단과 이어지는 관계를 분명하게 만들어야 한다.',
    '문장을 짧게 줄이더라도 책임 주체와 필요한 조건은 빠뜨리지 않아야 한다.',
    '자동화 결과에는 사용한 기준과 출력 파일의 위치를 함께 적어 다시 확인하기 쉽게 한다.',
    '문장 표본의 개수가 부족하면 결과를 확정하지 말고 더 많은 자료를 모아야 한다.',
    '초안을 여러 차례 읽을 때는 한 번에 한 가지 기준에 집중하는 것이 효과적이다.',
)


def strip_frontmatter(text):
    delimiter = '-' * 3
    if text.startswith(delimiter):
        parts = text.split(delimiter, 2)
        if len(parts) == 3:
            return parts[2]
    return text


def html_to_lines(raw_html):
    cleaned = HTML_STRIP_BLOCKS.sub('\n', raw_html)
    cleaned = HTML_BLOCK_END.sub('\n', cleaned)
    cleaned = HTML_TAG.sub(' ', cleaned)
    cleaned = html.unescape(cleaned)
    lines = []
    for line in cleaned.split('\n'):
        line = MULTI_SPACE.sub(' ', line).strip()
        if line:
            lines.append(line)
    return '\n'.join(lines)


def strip_non_prose_blocks(text):
    """펜스 코드와 HTML 코드 블록을 문장 추출 전에 제거한다."""
    lines = []
    fence_character = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        match = FENCE_LINE.match(line.rstrip('\r\n'))
        if fence_character:
            if (
                match
                and match.group(1)[0] == fence_character
                and len(match.group(1)) >= fence_length
                and not match.group(2).strip()
            ):
                fence_character = None
                fence_length = 0
            continue
        if match:
            fence_character = match.group(1)[0]
            fence_length = len(match.group(1))
            continue
        lines.append(line)
    return HTML_CODE_BLOCKS.sub('\n', ''.join(lines))


def strip_inline_markdown(text):
    """표시 문법만 걷어 내고 초안의 문장 텍스트를 보존한다."""
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    text = re.sub(r'\[\^[^\]]+\]', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'(\*\*|__|~~)(.*?)\1', r'\2', text)
    text = re.sub(r'(?<!\w)\*([^*]+)\*', r'\1', text)
    return re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', text)


def register_of(sent):
    """문장의 문체를 plain 또는 polite로 구분한다."""
    if sent.endswith(POLITE_EXCEPT):
        return 'plain'
    if POLITE_RE.search(sent):
        return 'polite'
    return 'plain'


def is_prose(sent):
    """산문 문장인지 확인해 마크다운 조각과 표 파편을 거른다."""
    if not sent.endswith(SENT_END):
        return False
    for bad in ('**', '*', '](', '|', '`', '[^', '~~', '<'):
        if bad in sent:
            return False
    return True


def iter_sentences(path, min_len, max_len, prose_only=True):
    with io.open(path, encoding='utf-8') as source:
        raw = source.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.html', '.htm'):
        text = html_to_lines(strip_non_prose_blocks(raw))
    else:
        text = strip_non_prose_blocks(strip_frontmatter(raw))
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith(SKIP_PREFIX):
            continue
        if line.startswith('*') and line.endswith('*'):
            continue
        line = NUM_MARKER.sub('', line)
        line = BULLET_MARKER.sub('', line)
        for sent in SPLIT.split(line):
            sent = sent.strip()
            if not sent:
                continue
            if prose_only and not is_prose(sent):
                continue
            if min_len <= len(sent) <= max_len:
                yield sent


def iter_draft_sentences(path, min_len=4, max_len=400):
    """초안에서 완결문과 길이가 충분한 어구를 추출한다."""
    with io.open(path, encoding='utf-8') as source:
        raw = source.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.html', '.htm'):
        text = html_to_lines(strip_non_prose_blocks(raw))
    else:
        text = strip_non_prose_blocks(strip_frontmatter(raw))
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith(DRAFT_SKIP_PREFIX):
            continue
        if REFERENCE_DEFINITION.match(line):
            continue
        line = NUM_MARKER.sub('', line)
        line = DRAFT_BULLET_MARKER.sub('', line)
        line = strip_inline_markdown(line)
        for sent in SPLIT.split(line):
            sent = sent.strip()
            if not sent or len(sent) > max_len:
                continue
            complete = sent.endswith(SENT_END) or re.search(r'[.!?]["\'\)\]]*$', sent)
            minimum = min_len if complete else 12
            if len(sent) >= minimum:
                yield sent


def dominant_register(sentences):
    polite = sum(1 for sentence in sentences if register_of(sentence) == 'polite')
    return 'polite' if polite * 2 > len(sentences) else 'plain'


def resolve_corpus_dir(explicit_dir, draft_path):
    if explicit_dir:
        return os.path.abspath(os.path.expanduser(explicit_dir))
    current = os.path.abspath(os.path.dirname(draft_path))
    for _ in range(4):
        if any(
            os.path.isdir(os.path.join(current, 'content', section))
            for section in ('digest', 'posts')
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def supported_files(directory):
    return [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS
        and os.path.isfile(os.path.join(directory, name))
    ]


def should_exclude(path, exclude, draft_path):
    absolute_path = os.path.abspath(path)
    slug = os.path.splitext(os.path.basename(path))[0]
    excluded_paths = {os.path.abspath(item) for item in exclude if os.path.isabs(item)}
    excluded_slugs = {item for item in exclude if not os.path.isabs(item)}
    excluded_slugs.update(('ref_corpus', 'draft_sents'))
    return absolute_path == draft_path or absolute_path in excluded_paths or slug in excluded_slugs


def collect_reference(corpus_dir, exclude, count, seed, want_register, draft_path=None):
    """최근 글에서 초안과 같은 문체의 산문 표본을 모은다."""
    if not corpus_dir or not os.path.isdir(corpus_dir):
        return []

    excluded = set(exclude)
    if draft_path:
        excluded.add(os.path.abspath(draft_path))

    section_dirs = [
        os.path.join(corpus_dir, 'content', section)
        for section in ('digest', 'posts')
        if os.path.isdir(os.path.join(corpus_dir, 'content', section))
    ]
    pool = []

    if section_dirs:
        for directory in section_dirs:
            files = supported_files(directory)
            files.sort(key=os.path.getmtime, reverse=True)
            for path in files[:20]:
                if should_exclude(path, excluded, draft_path):
                    continue
                for sentence in iter_sentences(path, 25, 120):
                    if register_of(sentence) == want_register:
                        pool.append(sentence)
    else:
        files = []
        for root, directories, names in os.walk(corpus_dir):
            directories[:] = [
                name for name in directories
                if name not in SKIP_DIRECTORIES and not name.startswith('.')
            ]
            for name in names:
                if os.path.splitext(name)[1].lower() not in SUPPORTED_EXTENSIONS:
                    continue
                path = os.path.join(root, name)
                if os.path.isfile(path) and not should_exclude(path, excluded, draft_path):
                    files.append(path)
        files.sort(key=os.path.getmtime, reverse=True)
        for path in files[:40]:
            for sentence in iter_sentences(path, 25, 120):
                if register_of(sentence) == want_register:
                    pool.append(sentence)

    random.Random(seed).shuffle(pool)
    return pool[:count]


def fallback_sentences(register, existing):
    defaults = DEFAULT_POLITE_CORPUS if register == 'polite' else DEFAULT_PLAIN_CORPUS
    result = list(existing)
    if not result:
        return list(defaults)
    for sentence in defaults:
        if sentence not in result:
            result.append(sentence)
        if len(result) >= MIN_REFERENCE_SENTENCES:
            break
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='문체 비교용 기준 문장과 초안 문장 생성')
    parser.add_argument(
        '--corpus-dir', '--blog-root', dest='corpus_dir', default=None,
        help='기준 문장을 수집할 문서 디렉터리',
    )
    parser.add_argument(
        '--draft', required=True,
        help='채점할 초안 파일 경로 (.md, .txt, .html, .htm)',
    )
    parser.add_argument('--out-dir', default=None, help='출력 디렉터리')
    parser.add_argument('--ref-count', type=int, default=45, help='기준 문장 수')
    parser.add_argument(
        '--register', choices=('plain', 'polite'), default=None,
        help='기준 코퍼스 문체. 생략하면 초안에서 판정한다.',
    )
    parser.add_argument(
        '--top-pct', type=float, default=0.05,
        help='재작성 대상 상위 비율. 기본 0.05, 논점형 글은 0.10',
    )
    parser.add_argument('--exclude', nargs='*', default=[], help='제외할 파일명 slug 목록')
    parser.add_argument('--seed', type=int, default=11, help='문장 표본 난수 시드')
    parser.add_argument(
        '--allow-empty-corpus', action='store_true',
        help='기준 문장이 부족하면 내장 기준선으로 보충한다.',
    )
    args = parser.parse_args(argv)

    draft_path = os.path.abspath(os.path.expanduser(args.draft))
    extension = os.path.splitext(draft_path)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        sys.stderr.write('초안 파일은 .md, .txt, .html, .htm 형식이어야 한다.\n')
        return 2
    try:
        draft = list(iter_draft_sentences(draft_path))
    except (OSError, UnicodeError) as error:
        sys.stderr.write('초안을 읽을 수 없다: %s\n' % error)
        return 2
    if not draft:
        sys.stderr.write('초안에서 문장을 찾지 못했다. --draft 경로를 확인하라.\n')
        return 2

    register = args.register or dominant_register(draft)
    corpus_dir = resolve_corpus_dir(args.corpus_dir, draft_path)
    exclude = set(args.exclude)
    exclude.add(draft_path)
    reference = collect_reference(
        corpus_dir, exclude, args.ref_count, args.seed, register, draft_path=draft_path,
    )
    user_ref_sentence_count = len(reference)
    use_fallback = args.allow_empty_corpus or (args.corpus_dir is None and corpus_dir is None)

    if len(reference) < MIN_REFERENCE_SENTENCES and use_fallback:
        reference = fallback_sentences(register, reference)
    builtin_ref_sentence_count = len(reference) - user_ref_sentence_count
    if len(reference) < MIN_REFERENCE_SENTENCES:
        sys.stderr.write(
            '기준 코퍼스가 %d문장뿐이다(문체 %s). '
            '--corpus-dir 경로나 --register를 확인하라.\n' % (len(reference), register)
        )
        return 2

    output_dir = args.out_dir or os.path.dirname(draft_path)
    output_dir = os.path.abspath(os.path.expanduser(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    reference_path = os.path.join(output_dir, 'ref_corpus.txt')
    draft_sentences_path = os.path.join(output_dir, 'draft_sents.txt')
    metadata_path = os.path.join(output_dir, 'probe_meta.json')
    register_label = '합쇼체/해요체' if register == 'polite' else '해라체'
    target_rewrite_count = max(1, round(len(draft) * args.top_pct))
    # The mode distinguishes user samples from built-in fallback sentences.
    if user_ref_sentence_count == 0:
        corpus_mode = 'empty'
    elif builtin_ref_sentence_count > 0:
        corpus_mode = 'mixed'
    else:
        corpus_mode = 'corpus'

    with io.open(reference_path, 'w', encoding='utf-8', newline='\n') as output:
        output.write('\n'.join('- ' + sentence for sentence in reference) + '\n')
    with io.open(draft_sentences_path, 'w', encoding='utf-8', newline='\n') as output:
        output.write('\n'.join(
            '%3d. %s' % (index + 1, sentence)
            for index, sentence in enumerate(draft)
        ) + '\n')
    metadata = {
        'register': register,
        'register_label': register_label,
        'corpus_mode': corpus_mode,
        'allow_empty_corpus': args.allow_empty_corpus,
        'ref_sentence_count': len(reference),
        'user_ref_sentence_count': user_ref_sentence_count,
        'builtin_ref_sentence_count': builtin_ref_sentence_count,
        'draft_sentence_count': len(draft),
        'top_pct': args.top_pct,
        'target_rewrite_count': target_rewrite_count,
    }
    with io.open(metadata_path, 'w', encoding='utf-8', newline='\n') as output:
        json.dump(metadata, output, ensure_ascii=False, indent=2)
        output.write('\n')

    percent_label = int(round(args.top_pct * 100))
    print('문체 판정  : %s' % register_label)
    if corpus_mode == 'empty':
        print('코퍼스 모드: 내장 기본 기준선 사용')
    elif corpus_mode == 'mixed':
        print(
            '코퍼스 모드: 사용자 코퍼스 + 내장 기본 기준선 혼합 '
            '(사용자 %d문장, 내장 %d문장)'
            % (user_ref_sentence_count, builtin_ref_sentence_count)
        )
    print('기준 코퍼스: %d문장 -> %s' % (len(reference), reference_path))
    print('초안 문장  : %d문장 -> %s' % (len(draft), draft_sentences_path))
    print('재작성 대상: 상위 %d문장 (%d%%)' % (target_rewrite_count, percent_label))
    return 0


if __name__ == '__main__':
    sys.exit(main())
