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
    
    # 2. Hardware-accelerated sliding indicator
    assert "translate3d" in content or "transform" in content
    assert "will-change-transform" in content or "transition" in content
    
    # 3. Dynamic measurement & resize observer
    assert "getBoundingClientRect" in content or "offsetLeft" in content
    assert "ResizeObserver" in content or "addEventListener('resize'" in content
    
    # 4. Telegram haptic feedback
    assert "telegram.hapticImpact" in content


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
    # Find loadData useCallback dependencies
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


def test_organizer_workspace_animated_segmented_contract():
    ws_path = FRONTEND_DIR / "src" / "components" / "OrganizerWorkspace.tsx"
    assert ws_path.exists(), "OrganizerWorkspace.tsx must exist"
    
    content = ws_path.read_text(encoding="utf-8")
    
    # 1. Imports and renders AnimatedSegmentedControl
    assert "AnimatedSegmentedControl" in content
    
    # 2. Has animate-tab-enter transition
    assert "animate-tab-enter" in content


def test_css_motion_and_reduced_motion_contract():
    css_path = FRONTEND_DIR / "src" / "index.css"
    assert css_path.exists(), "index.css must exist"
    
    content = css_path.read_text(encoding="utf-8")
    
    # 1. Keyframes and class definition
    assert "@keyframes tabEnter" in content
    assert ".animate-tab-enter" in content
    
    # 2. Reduced motion support
    assert "prefers-reduced-motion" in content
