import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IssueList } from '../features/issue-list/IssueList';
import { mapEventToIssue } from '../entities/issue/mapEventToIssue';
import { event } from './fixtures';
const issue = mapEventToIssue('r', event);
describe('issue list UI', () => {
  it('closes and reopens immediately with a checkbox', async () => {
    const user = userEvent.setup();
    const repository = {
      getAll: vi.fn().mockResolvedValue([]),
      setResolved: vi.fn().mockResolvedValue(undefined),
    };
    render(<IssueList issues={[issue]} repository={repository} />);
    const checkbox = screen.getByRole('checkbox');
    await user.click(checkbox);
    expect(checkbox).toBeChecked();
    await waitFor(() => expect(repository.setResolved).toHaveBeenCalledWith(issue.id, true));
    await user.click(checkbox);
    expect(checkbox).not.toBeChecked();
    expect(repository.setResolved).toHaveBeenLastCalledWith(issue.id, false);
  });
  it('rolls back on storage failure and shows an error', async () => {
    const user = userEvent.setup();
    render(
      <IssueList
        issues={[issue]}
        repository={{ getAll: vi.fn(), setResolved: vi.fn().mockRejectedValue(new Error('quota')) }}
      />,
    );
    await user.click(screen.getByRole('checkbox'));
    await waitFor(() => expect(screen.getByRole('checkbox')).not.toBeChecked());
    expect(screen.getByRole('alert')).toHaveTextContent('Изменение отменено');
  });
  it('preserves an optimistic status across repeated event props', async () => {
    const user = userEvent.setup();
    const repository = { getAll: vi.fn(), setResolved: vi.fn().mockResolvedValue(undefined) };
    const view = render(<IssueList issues={[issue]} repository={repository} />);
    await user.click(screen.getByRole('checkbox'));
    view.rerender(<IssueList issues={[{ ...issue }]} repository={repository} />);
    expect(screen.getByRole('checkbox')).toBeChecked();
  });
  it('filters by description and status, with open issues first', async () => {
    const user = userEvent.setup();
    render(
      <IssueList
        issues={[
          { ...issue, resolved: true },
          mapEventToIssue('r', { ...event, type: 'GAP', start_ms: 3000 }),
        ]}
      />,
    );
    expect(screen.getAllByRole('checkbox')[0]).not.toBeChecked();
    await user.selectOptions(screen.getByLabelText('Статус'), 'closed');
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    await user.type(screen.getByPlaceholderText('Поиск по сообщению или описанию'), 'nothing');
    expect(screen.getByText('Проблем не найдено')).toBeInTheDocument();
  });
  it('renders loading, empty and error states', () => {
    const view = render(<IssueList issues={[]} loading />);
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка');
    view.rerender(<IssueList issues={[]} />);
    expect(screen.getByText('Проблем не найдено')).toBeInTheDocument();
    view.rerender(<IssueList issues={[]} error={new Error('Backend недоступен')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Backend недоступен');
  });
});
