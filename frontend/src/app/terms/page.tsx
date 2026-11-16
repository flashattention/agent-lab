import type { Metadata } from "next";
import Link from "next/link";
import { CONTACT_URL, LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = { title: "서비스 약관" };

export default function TermsPage() {
  return (
    <LegalPage title="서비스 약관">
      <p>
        AgentLab(이하 &ldquo;서비스&rdquo;)은 AI Agent 학습을 위한 비상업적 개인 프로젝트입니다. 서비스를 이용하면 아래 약관에 동의한 것으로
        봅니다.
      </p>

      <section>
        <h2>1. 서비스 내용</h2>
        <p>서비스는 AI Agent 강의, 브라우저에서 실행하는 실습 코드, 비주얼 그래프 플레이그라운드, 프로젝트 저장과 공유 기능을 무료로 제공합니다.</p>
      </section>

      <section>
        <h2>2. OpenAI API 키와 비용</h2>
        <p>
          코드 실행에는 사용자 본인의 OpenAI API 키가 쓰이며, 그로 인해 발생하는 OpenAI 요금은 사용자가 부담합니다. 키 관리 책임은 사용자에게
          있습니다.
        </p>
      </section>

      <section>
        <h2>3. 금지 행위</h2>
        <ul>
          <li>실행 환경을 이용한 외부 시스템 공격, 스팸, 불법 콘텐츠 생성</li>
          <li>실행 한도 우회, 서버에 과도한 부하를 주는 자동화된 요청</li>
          <li>타인의 권리를 침해하는 내용을 저장하거나 공유하는 행위</li>
        </ul>
        <p>위반이 확인되면 사전 통지 없이 이용을 제한하거나 데이터를 삭제할 수 있습니다.</p>
      </section>

      <section>
        <h2>4. 이용 한도</h2>
        <p>안정적인 운영을 위해 사용자별 하루 실행·검증·고도화 횟수에 한도가 있으며, 운영 상황에 따라 바뀔 수 있습니다.</p>
      </section>

      <section>
        <h2>5. 콘텐츠</h2>
        <p>
          사용자가 만든 프로젝트의 권리는 사용자에게 있습니다. 공유를 켠 프로젝트는 링크를 가진 누구나 볼 수 있습니다. 강의와 문서 내용은 학습
          목적으로 자유롭게 참고할 수 있습니다.
        </p>
      </section>

      <section>
        <h2>6. 면책</h2>
        <p>
          서비스는 &ldquo;있는 그대로&rdquo; 제공됩니다. 서비스 중단, 데이터 손실, 실행 결과의 정확성에 대해 보증하지 않으며, 예고 없이 기능이
          바뀌거나 서비스가 종료될 수 있습니다. 중요한 코드는 별도로 보관해 주세요.
        </p>
      </section>

      <section>
        <h2>7. 개인정보와 문의</h2>
        <p>
          개인정보 처리는 <Link href="/privacy">개인정보처리방침</Link>을 따릅니다. 문의는 <a href={CONTACT_URL}>GitHub Issues</a>로 보내 주세요.
        </p>
      </section>
    </LegalPage>
  );
}
