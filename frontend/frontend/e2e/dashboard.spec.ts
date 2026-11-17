import { test, expect, type Page } from '@playwright/test';
import { metrics, point } from '../src/test/fixtures';
async function mockApi(page: Page) {
  const now = Date.now();
  const robotId = 'AMR-042';
  const points = Array.from({ length: 180 }, (_, i) =>
    point(now - (180 - i) * 1000, {
      pose: {
        x: 4 + Math.cos(i / 25) * 4 + i / 45,
        y: 3 + Math.sin(i / 25) * 2,
        yaw: i / 25 + Math.PI / 2,
      },
      cmd_vel: { linear_x: 0.8, angular_z: 0.12 },
      odom_vel: {
        linear_x: 0.75 + Math.sin(i / 12) * 0.1,
        angular_z: 0.1 + Math.cos(i / 15) * 0.04,
      },
    }),
  );
  const robot = {
    id: robotId,
    online: true,
    first_seen_ms: now - 600000,
    last_seen_ms: now,
    last_point_ms: now - 1000,
    total_points: 180,
    total_batches: 18,
    last_point: points.at(-1),
  };
  const events = [
    {
      type: 'NOTF',
      start_ms: now - 70000,
      end_ms: now - 65000,
      duration_s: 5,
      samples: 5,
      message: 'map → base_link transform unavailable',
    },
    {
      type: 'GAP',
      start_ms: now - 130000,
      end_ms: now - 125000,
      duration_s: 5,
      samples: 0,
      message: null,
    },
  ];
  await page.route('http://localhost:8000/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const base = { robot_id: robotId, from_ms: now - 600000, to_ms: now };
    const data =
      path === '/api/robots'
        ? [robot]
        : path.endsWith('/telemetry')
          ? { ...base, total_in_range: points.length, stride: 1, points }
          : path.endsWith('/trajectory')
            ? { ...base, points: points.map((p) => ({ t: p.timestamp_ms, ...p.pose })) }
            : path.endsWith('/metrics/timeseries')
              ? {
                  ...base,
                  bucket_s: 10,
                  buckets: Array.from({ length: 18 }, (_, i) => ({
                    t: now - (18 - i) * 10000,
                    samples: 10,
                    tf_availability: i === 9 ? 0.5 : 1,
                    distance_m: 7,
                    avg_speed_mps: 0.75,
                    avg_cmd_speed_mps: 0.8,
                    avg_angular_speed_rps: 0.1,
                    linear_rmse: 0.08 + Math.sin(i) * 0.03,
                    angular_rmse: 0.02 + Math.cos(i) * 0.01,
                  })),
                }
              : path.endsWith('/metrics')
                ? { ...metrics(robotId), samples: 180, duration_s: 180, distance_m: 24.6 }
                : path.endsWith('/events')
                  ? { ...base, events }
                  : robot;
    await route.fulfill({ json: data });
  });
  await page.routeWebSocket('ws://localhost:8000/ws/live*', (socket) => {
    socket.send(
      JSON.stringify({
        robot_id: robotId,
        points: [point(now, { pose: { x: 10, y: 5, yaw: 0.4 } })],
      }),
    );
  });
}
test('dashboard, persistence, responsive layout and live data', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await mockApi(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Карта движения' })).toBeVisible();
  await expect(page.getByText('Подключено', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Потеря координат' })).toBeVisible();
  const checkbox = page.getByRole('checkbox').first();
  await checkbox.check();
  await expect(checkbox).toBeEnabled();
  await page.reload();
  await expect(page.getByRole('checkbox').last()).toBeChecked();
  await expect(page.getByText('Подключено', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Следовать за роботом' }).click();
  await expect(page.getByRole('button', { name: 'Следовать за роботом' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Переключить тему' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('dashboard-mobile.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
test('unavailable backend remains visible as an error', async ({ page }) => {
  await page.route('http://localhost:8000/api/**', (route) => route.abort('connectionrefused'));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Backend недоступен', { timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Обновить' })).toBeVisible();
});
test('reload while backend is offline restores telemetry and local issue status', async ({
  page,
}) => {
  await mockApi(page);
  await page.goto('/');
  await expect(page.getByText('Подключено', { exact: true })).toBeVisible();
  const checkbox = page.getByRole('checkbox').first();
  await checkbox.check();
  await expect(checkbox).toBeEnabled();
  await page.route('http://localhost:8000/api/**', (route) => route.abort('connectionrefused'));
  await page.routeWebSocket('ws://localhost:8000/ws/live*', (socket) => socket.close());
  await page.reload();
  await expect(page.getByRole('checkbox').last()).toBeChecked();
  await expect(page.getByRole('heading', { name: 'Карта движения' })).toBeVisible();
  await expect(
    page
      .getByText('Backend недоступен или браузер заблокировал запрос (возможен CORS).', {
        exact: true,
      })
      .first(),
  ).toBeVisible();
  await expect(page.locator('.coordinates')).toContainText('10');
  await expect(page.locator('.map-canvas polyline')).toHaveAttribute('points', /[0-9]+/);
});
