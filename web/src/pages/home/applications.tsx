import { CardSineLineContainer } from '@/components/card-singleline-container';
import { EmptyCardType } from '@/components/empty/constant';
import { EmptyAppCard } from '@/components/empty/empty';
import { HomeIcon } from '@/components/svg-icon';
import { Routes } from '@/routes';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'umi';
import { SeeAllAppCard } from './application-card';
import { ChatList } from './chat-list';

export function Applications() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listLength, setListLength] = useState(0);
  const [loading, setLoading] = useState(false);

  const handleNavigate = useCallback(
    ({ isCreate }: { isCreate?: boolean }) => {
      if (isCreate) {
        navigate(Routes.Chats + '?isCreate=true');
      } else {
        navigate(Routes.Chats);
      }
    },
    [navigate],
  );

  return (
    <section className="mt-12">
      <div className="flex justify-between items-center mb-5">
        <h2 className="text-2xl font-semibold flex gap-2.5">
          <HomeIcon name="chats" width={'32'} />
          {t('chat.chatApps')}
        </h2>
      </div>
      <CardSineLineContainer>
        <ChatList
          setListLength={(length: number) => setListLength(length)}
          setLoading={(loading: boolean) => setLoading(loading)}
        ></ChatList>
        {listLength > 0 && (
          <SeeAllAppCard
            click={() => handleNavigate({ isCreate: false })}
          ></SeeAllAppCard>
        )}
      </CardSineLineContainer>
      {listLength <= 0 && !loading && (
        <EmptyAppCard
          type={EmptyCardType.Chat}
          onClick={() => handleNavigate({ isCreate: true })}
        />
      )}
    </section>
  );
}
