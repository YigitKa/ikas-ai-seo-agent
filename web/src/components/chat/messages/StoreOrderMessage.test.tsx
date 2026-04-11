import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AssistantMessageContent from './AssistantContent';
import { parseStoreOrderMessage } from './storeOrderMessageParser';

describe('parseStoreOrderMessage', () => {
  it('parses legacy recent order markdown with collapsed extra item text', () => {
    const parsed = parseStoreOrderMessage(`**Son Siparisler**
- Gosterilen siparis: 2
- #2760 | 09.04.2026 10:28 | durum: CREATED | odeme: PAID | toplam: 26046.39 | musteri: - | urunler: Canna Terra Professional 50 Litre x4, Voodoo Juice 500 mL x2, +6 urun daha

**Not**
- Bu liste ikas MCP canli verisinden dogrudan alindi.`);

    expect(parsed).not.toBeNull();
    expect(parsed?.kind).toBe('recent_orders');
    expect(parsed?.orders[0]).toMatchObject({
      orderNumber: '2760',
      status: 'CREATED',
      paymentStatus: 'PAID',
      extraItemsText: '+6 urun daha',
    });
  });

  it('parses all order items when the payload uses the full item separator', () => {
    const parsed = parseStoreOrderMessage(`**Son Siparisler**
- Gosterilen siparis: 1
- #2763 | 05.04.2026 00:10 | durum: DRAFT | odeme: WAITING | toplam: 187736.30 | musteri: - | urunler: Tarantula 5 Litre x1 || B-52 5 Litre x1 || Rhino Skin 5 Litre x1 || Sensi Cal-Mag Xtra 5 Litre x1
`);

    expect(parsed?.orders[0].items).toEqual([
      'Tarantula 5 Litre x1',
      'B-52 5 Litre x1',
      'Rhino Skin 5 Litre x1',
      'Sensi Cal-Mag Xtra 5 Litre x1',
    ]);
    expect(parsed?.orders[0].extraItemsText).toBeUndefined();
  });
});

describe('StoreOrderMessage rendering', () => {
  it('renders recent orders as a designed card and expands hidden products on demand', async () => {
    const user = userEvent.setup();

    render(
      <AssistantMessageContent
        content={`**Son Siparisler**
- Gosterilen siparis: 2
- #2760 | 09.04.2026 10:28 | durum: CREATED | odeme: PAID | toplam: 26046.39 | musteri: - | urunler: Canna Terra Professional 50 Litre x4 || Voodoo Juice 500 mL x2 || Rhino Skin 5 Litre x1 || Sensi Cal-Mag Xtra 5 Litre x1
- #2770 | 08.04.2026 16:15 | durum: CREATED | odeme: PAID | toplam: 300.56 | musteri: - | urunler: Growth Technology Cactus Focus x1

**Not**
- Bu liste ikas MCP canli verisinden dogrudan alindi.`}
      />,
    );

    expect(screen.getByText('Siparis Akisi')).toBeInTheDocument();
    expect(screen.getByText('Son Siparisler')).toBeInTheDocument();
    expect(screen.getByText('26.046,39')).toBeInTheDocument();
    expect(screen.getAllByText('Odendi').length).toBeGreaterThan(0);
    expect(screen.getByText('Canna Terra Professional 50 Litre x4')).toBeInTheDocument();
    expect(screen.getByText('Voodoo Juice 500 mL x2')).toBeInTheDocument();
    expect(screen.queryByText('Rhino Skin 5 Litre x1')).not.toBeInTheDocument();
    expect(screen.queryByText('Sensi Cal-Mag Xtra 5 Litre x1')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '+2 urun daha' })).toBeInTheDocument();
    expect(screen.queryByText(/#2760 \| 09\.04\.2026 10:28 \| durum:/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '+2 urun daha' }));

    expect(screen.getByText('Rhino Skin 5 Litre x1')).toBeInTheDocument();
    expect(screen.getByText('Sensi Cal-Mag Xtra 5 Litre x1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Daralt' })).toHaveAttribute('aria-expanded', 'true');
  });
});
