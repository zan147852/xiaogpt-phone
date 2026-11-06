"""Run without XiaoGPT or network to check conservative confirmation behavior."""
import time
import uuid
import shutil
from contextlib import contextmanager
from pathlib import Path

from local_memory import MemoryStore, find_memory_candidate


@contextmanager
def test_directory():
    directory = Path(__file__).parent / ('check-state-' + uuid.uuid4().hex)
    directory.mkdir(mode=0o755)
    try:
        yield directory
    finally:
        assert directory.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(directory)


def check():
    assert find_memory_candidate('我喜欢清淡的饭菜，你能推荐一些吗？') == '我喜欢清淡的饭菜'
    assert find_memory_candidate('如果我喜欢清淡的饭菜怎么办') is None
    assert find_memory_candidate('我朋友喜欢爬山') is None
    assert find_memory_candidate('我喜欢存款很多的人') is None
    assert find_memory_candidate('我喜欢哪个菜呢') is None
    assert find_memory_candidate('请帮我推荐早餐我喜欢早上吃面条') == '我喜欢早上吃面条'
    assert find_memory_candidate('帮我推荐早餐我喜欢早上吃面条你能给我点建议吗') == '我喜欢早上吃面条'
    assert find_memory_candidate('请翻译我喜欢早上吃面条') is None
    assert find_memory_candidate('请给我一个故事角色说我喜欢早上吃面条') is None
    assert find_memory_candidate('请给我建议如果我喜欢早上吃面条怎么办') is None
    with test_directory() as directory:
        memory = MemoryStore(Path(directory) / 'memory.sqlite3')
        assert memory.propose('我喜欢清淡的饭菜')
        assert memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 0
        assert memory.handle('不要记') == '好，这条没有保存。'
        assert memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 0
        memory.proposal_cooldown = 0
        assert memory.propose('我每天晚上散步')
        assert '记住了' in memory.handle('记住这条')
        assert '散步' in memory.context('运动建议')
        assert '没有等待确认' in memory.handle('记住这条')
        memory.proposal_cooldown = 0
        assert memory.propose('我周末喜欢骑车')
        memory.pending_until = time.monotonic() - 1
        assert '没有等待确认' in memory.handle('确认记住')
        assert memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 1
        memory.proposal_cooldown = 0
        assert memory.propose('我平时喜欢游泳')
        assert memory.handle('明天天气怎样') is None
        assert '没有等待确认' in memory.handle('记住这条')
        assert memory.connection.execute('SELECT COUNT(*) FROM notes').fetchone()[0] == 1
        memory.close()
        memory = MemoryStore(Path(directory) / 'memory.sqlite3')
        assert '散步' in memory.context('运动建议')
        assert memory.pending_memory is None
        memory.close()
    print('Automatic memory candidates / explicit confirmation / rejection / expiry / restart: PASS (offline)')


check()
