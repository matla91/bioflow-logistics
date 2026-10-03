import assert from 'node:assert/strict';
import test from 'node:test';
import { createRenderer, h } from 'vue';

let moduleId = 0;

async function appearanceEnvironment(t, { authenticated, saved, systemDark }) {
    const original = {
        window: globalThis.window,
        document: globalThis.document,
        localStorage: globalThis.localStorage,
    };
    t.after(() => Object.assign(globalThis, original));

    const classes = new Set();
    const storage = new Map(saved ? [['appearance', saved]] : []);
    const listeners = [];
    const media = {
        matches: systemDark,
        addEventListener: (_, listener) => listeners.push(listener),
    };

    globalThis.window = { matchMedia: () => media };
    globalThis.document = {
        documentElement: {
            dataset: authenticated ? { theme: 'dark' } : {},
            classList: {
                add: (name) => classes.add(name),
                toggle: (name, enabled) =>
                    enabled ? classes.add(name) : classes.delete(name),
            },
        },
    };
    globalThis.localStorage = {
        getItem: (name) => storage.get(name) ?? null,
        setItem: (name, value) => storage.set(name, value),
    };

    const theme = await import(
        `../../resources/js/composables/useAppearance.ts?case=${moduleId++}`
    );

    return {
        theme,
        isDark: () => classes.has('dark'),
        systemChange: (dark) => {
            media.matches = dark;
            listeners.forEach((listener) => listener());
        },
    };
}

for (const saved of ['light', 'system']) {
    void test(`authenticated startup ignores ${saved} appearance on a light OS`, async (t) => {
        const env = await appearanceEnvironment(t, {
            authenticated: true,
            saved,
            systemDark: false,
        });
        env.theme.initializeTheme();
        assert.equal(env.isDark(), true);
        env.systemChange(true);
        env.systemChange(false);
        assert.equal(env.isDark(), true);
        assert.equal(localStorage.getItem('appearance'), saved);
    });
}

for (const [saved, systemDark, expectedDark] of [
    ['light', true, false],
    ['dark', false, true],
    ['system', false, false],
    [null, true, true],
]) {
    void test(`guest startup respects ${saved ?? 'default system'} appearance`, async (t) => {
        const env = await appearanceEnvironment(t, {
            authenticated: false,
            saved,
            systemDark,
        });
        env.theme.initializeTheme();
        assert.equal(env.isDark(), expectedDark);
        env.systemChange(!systemDark);
        assert.equal(
            env.isDark(),
            saved === 'system' || saved === null ? !systemDark : expectedDark,
        );
    });
}

void test('Inertia shell mounting forces dark and logout restores the guest preference', async (t) => {
    const env = await appearanceEnvironment(t, {
        authenticated: false,
        saved: 'light',
        systemDark: false,
    });
    env.theme.initializeTheme();
    assert.equal(env.isDark(), false);

    const renderer = createRenderer({
        createElement: () => ({}),
        createText: () => ({}),
        createComment: () => ({}),
        insert: () => {},
        remove: () => {},
        patchProp: () => {},
        setText: () => {},
        setElementText: () => {},
        parentNode: () => null,
        nextSibling: () => null,
    });
    let appearance;
    const app = renderer.createApp({
        setup() {
            env.theme.useSmartflowTheme();
            appearance = env.theme.useAppearance();
            return () => h('div');
        },
    });
    app.mount({});

    assert.equal(env.isDark(), true);
    assert.equal(appearance.resolvedAppearance.value, 'dark');
    appearance.updateAppearance('light');
    env.systemChange(false);
    assert.equal(env.isDark(), true);
    assert.equal(appearance.resolvedAppearance.value, 'dark');

    app.unmount();
    assert.equal(env.isDark(), false);
    assert.equal(appearance.resolvedAppearance.value, 'light');
    assert.equal(document.documentElement.dataset.theme, undefined);
    assert.equal(localStorage.getItem('appearance'), 'light');
});
