from pathlib import Path
import re
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_animated_segmented_control_contract():
    ctrl_path = FRONTEND_DIR / "src" / "components" / "AnimatedSegmentedControl.tsx"
    assert ctrl_path.exists(), "AnimatedSegmentedControl.tsx component must exist"
    
    content = ctrl_path.read_text(encoding="utf-8")
    
    # 1. Accessibility ARIA attributes
    assert 'role="tablist"' in content
    assert 'role="tab"' in content
    assert 'aria-selected=' in content
    
    # 2. Hardware-accelerated sliding indicator with Y=0 in translate3d
    assert "translate3d" in content
    assert "translate3d(${indicator.left}px, 0, 0)" in content
    assert "top-0 left-0" in content
    assert "will-change" in content or "transition" in content
    
    # 3. Dynamic measurement uses layout offsets (immune to parent animations)
    assert "offsetLeft" in content
    assert "offsetWidth" in content
    assert "offsetTop" in content
    assert "offsetHeight" in content
    assert "ResizeObserver" in content
    
    # 4. Telegram haptic feedback
    assert "telegram.hapticImpact" in content

    # 5. Responsive scrollable support
    assert "scrollable" in content
    assert "overflow-x-auto" in content


def test_event_company_modal_stable_sheet_contract():
    modal_path = FRONTEND_DIR / "src" / "components" / "EventCompanyModal.tsx"
    assert modal_path.exists(), "EventCompanyModal.tsx must exist"
    
    content = modal_path.read_text(encoding="utf-8")
    
    # 1. Uses AnimatedSegmentedControl
    assert "AnimatedSegmentedControl" in content
    
    # 2. Outer container has stable height/frame
    assert "h-[84vh]" in content
    assert "max-h-[92vh]" in content
    assert "flex flex-col" in content
    
    # 3. Content viewport is scrollable and pinned
    assert "flex-1 min-h-0 overflow-y-auto" in content
    assert "animate-tab-enter" in content
    
    # 4. loadData does not re-fetch on activeTab change
    load_data_match = re.search(r"const loadData = useCallback\(async\s*\(.*?\)\s*=>.*?\}, \[(.*?)\]\);", content, re.DOTALL)
    assert load_data_match is not None, "loadData useCallback should exist"
    deps = load_data_match.group(1)
    assert "activeTab" not in deps, "loadData must NOT depend on activeTab to avoid unnecessary refetches"


def test_organizer_tab_animated_segmented_contract():
    tab_path = FRONTEND_DIR / "src" / "components" / "OrganizerTab.tsx"
    assert tab_path.exists(), "OrganizerTab.tsx must exist"
    
    content = tab_path.read_text(encoding="utf-8")
    
    # 1. Imports and renders AnimatedSegmentedControl
    assert "AnimatedSegmentedControl" in content
    assert "attending" in content
    assert "interested" in content
    assert "subscriptions" in content
    
    # 2. Has animate-tab-enter transition
    assert "animate-tab-enter" in content


def test_organizer_workspace_full_labels_and_scrollable_contract():
    ws_path = FRONTEND_DIR / "src" / "components" / "OrganizerWorkspace.tsx"
    assert ws_path.exists(), "OrganizerWorkspace.tsx must exist"
    
    content = ws_path.read_text(encoding="utf-8")
    
    # 1. Imports and renders AnimatedSegmentedControl with scrollable
    assert "AnimatedSegmentedControl" in content
    assert "scrollable" in content
    
    # 2. Full required labels without abbreviations or truncations
    assert "Обзор" in content
    assert "Мероприятия" in content
    assert "Места" in content
    assert "Аудитория" in content
    assert "Рассылки" in content
    
    # 3. Has animate-tab-enter transition
    assert "animate-tab-enter" in content


def test_afisha_date_filter_animated_segmented_contract():
    filter_path = FRONTEND_DIR / "src" / "components" / "FilterBar.tsx"
    assert filter_path.exists(), "FilterBar.tsx must exist"
    
    content = filter_path.read_text(encoding="utf-8")
    
    # 1. Uses AnimatedSegmentedControl for date filters
    assert "AnimatedSegmentedControl" in content
    assert "dateFilter" in content
    assert "Все даты" in content
    assert "Сегодня" in content
    assert "Завтра" in content
    assert "Выходные" in content


def test_bottom_navigation_sliding_indicator_contract():
    nav_path = FRONTEND_DIR / "src" / "components" / "Navigation.tsx"
    assert nav_path.exists(), "Navigation.tsx must exist"
    
    content = nav_path.read_text(encoding="utf-8")
    
    # 1. Has active sliding indicator with translate3d
    assert "translate3d" in content
    assert "indicator" in content
    assert "offsetLeft" in content
    assert "offsetWidth" in content
    assert "offsetTop" in content
    assert "offsetHeight" in content
    
    # 2. Supports all tabs including feed, my_events, and admin
    assert "feed" in content
    assert "my_events" in content
    assert "admin" in content
    assert "isAdmin" in content
    
    # 3. Telegram haptics
    assert "telegram.hapticImpact" in content


def test_css_motion_and_reduced_motion_contract():
    css_path = FRONTEND_DIR / "src" / "index.css"
    assert css_path.exists(), "index.css must exist"
    
    content = css_path.read_text(encoding="utf-8")
    
    # 1. Keyframes and class definition
    assert "@keyframes tabEnter" in content
    assert ".animate-tab-enter" in content
    
    # 2. Reduced motion support
    assert "prefers-reduced-motion" in content
